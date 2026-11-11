# E12-A14：漂移检测算法校准与对照实验

日期：2026-11-11  
状态：合成数据基准原型；不是生产阈值认证。

## 研究问题

A13 使用 TV 距离作描述性诊断。A14 比较 TV、Pearson 卡方近似、精确二项检验、单侧 CUSUM 和扫描式变化点统计量。重点指标：稳定环境误报率、漂移检出率、检测延迟。不能只比较总体 accuracy。

## 实验生成器

固定种子生成五类二元流：稳定 Bernoulli、突变（0.2→0.5）、渐变、平稳自相关 Markov-like 流、控制对象污染（0.2→0.65）。默认 100 个 seed、100 时间步、变点位置 40。所有 detector 对相同 seed 的同一条序列评分，保证配对比较。

## 检测器

- TV：固定滑动窗口经验频率与基线概率的绝对差。
- Pearson：二元 Pearson 统计量，使用 df=1 的卡方尾概率。
- Exact binomial：概率排序的双侧精确二项 p 值。
- CUSUM：针对向上变化的单侧 log-likelihood 累积和。
- Change point：窗口内扫描切分点，比较单一频率与两段独立频率的似然比。

阈值目前是显式工程参数，尚未通过独立校准集选定；多次逐步查看造成的 alpha 膨胀也尚未校正。CUSUM 当前只对向上变化敏感。变化点扫描统计量阈值不应直接解释为校正后的显著性水平。

## 指标定义

- false_alarm_rate：稳定流或真实变点前首次报警比例。
- detection_rate：真实变点存在时，变点后首次报警比例。
- mean_detection_delay：首次变点后报警时间减去真实变点位置。
- alarm_rate：所有 episode 中曾报警的比例。

## 当前限制

1. 合成二元数据不能代表真实多类别测量协议。
2. 自相关场景使用不同生成机制，和 Bernoulli 零假设不匹配，主要用于暴露稳健性问题。
3. 控制污染实验只是单流压力测试，不等同于 A13 控制流/目标流完整因果识别。
4. 默认阈值未经校准；逐时点重复检验会放大误报。
5. 不包含缺失、延迟、类别新生、概念漂移多重并发等情况。

## 下一步校准方案

先用独立 null seeds 选择阈值，使稳定场景的 episode-level false alarm 达到预注册目标（如 5%）；随后锁定阈值，在未见 seeds 上报告检出率与延迟。按 drift magnitude、autocorrelation、control contamination 分层，报告 bootstrap 置信区间。最后扩展到多类别、双流配对控制和带测量误差的环境。

## 运行

`python -m prototype.e12a14_drift_detector_calibration --seeds 100 --start-seed 1 --json`

`python -m unittest tests.test_e12a14_drift_detector_calibration -v`
