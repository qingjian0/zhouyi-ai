# M41：类象因果机制的价值型停止与继续决策 v0.1

## 问题

自适应实验系统不仅要选择下一项实验，还要决定何时停止。固定置信阈值容易忽略继续实验的未来价值；单纯追求 EIG 又可能导致无限追加实验。

## 决策契约

- STOP：当前终端决策效用不低于继续实验的净期望价值，且达到声明的置信要求；达到最大实验轮数时强制停止并明确记录。
- CONTINUE：继续实验的预期未来奖励扣除成本、风险和模型不确定性惩罚后，超过当前停止价值及预设 margin。
- REVIEW：当前置信不足，同时继续实验也不合格或无明显价值。
- 验证数据必须锁定；缺少证据引用或数值无效时拒绝自动决策。

公式：stop_value = expected_reward − expected_decision_loss；continue_value = expected_future_reward − experiment_cost − experiment_risk − uncertainty_penalty。

## 古典方法论

《墨子·小取》将“处利害，决嫌疑”纳入名辩与推类方法的任务。M41 将利害权衡落实为实验成本、风险、决策损失与继续价值的显式记录；这只是现代决策工程映射，不意味着先秦已有贝叶斯最优停止理论。

## 现代研究

Cheng & Huan, *Optimal Stopping for Sequential Bayesian Experimental Design* (arXiv:2509.21734, 2025; 2026 修订) 将实验设计与停止作为耦合的有限时域决策。Rossell (2013) 对高通量实验提出基于决策效用的序贯停止框架。Cook, Mishler & Ramdas (2024) 研究自适应实验中的 anytime-valid confidence sequences，说明数据依赖停止时需要与之相容的推断方法。

## 限制

M41 仅审计调用方提供的效用与风险估计，不估计未来奖励、不校准置信度、不生成置信序列、不保证频率学错误率、不证明因果真值，也不执行实验。实际推断必须把自适应分配和停止机制纳入分析。
