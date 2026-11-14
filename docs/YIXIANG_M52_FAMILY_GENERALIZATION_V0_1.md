# M52：跨机制家族泛化与泄漏审计 v0.1

## 研究问题

M51 的两类 SCM 验证了异质机制原型可以运行，但不能回答模型能否从训练家族泛化到未见机制家族。若随机拆分 episode，同一结构模板、生成器谱系或 seed 组可能同时进入训练集和测试集，导致结果被误读为 OOD 泛化。

M52 将拆分单位提升为整个因果家族，并提供按家族宏平均与配对家族 Bootstrap 的统计接口。

## 原子隔离规则

以下标识必须只属于一个 split：

- family_id：具体 SCM 家族。
- template_id：结构模板/生成规则族。
- generator_lineage_id：数据生成器实现谱系。
- seed_group_id：共享生成随机种子或种子派生组。
- episode_id：单条实验轨迹必须唯一。

mechanism_signature 记录机制类型供分层分析，不强制全局唯一；否则会把“同机制不同结构家族”的合理对照误判为泄漏。若研究目标是完全未见机制类型，应额外在实验协议层对 signature 做更严格的 split 限制。

## 统计接口

- family_macro_average：每个家族等权，避免样本量最大的家族主导总分。
- paired_family_bootstrap：以家族为 cluster 重采样，比较同一组 test families 上两个方法的配对差异；输出 percentile interval。
- 对照必须使用完全相同的 test family 集合，否则拒绝计算。

## 使用

```python
from prototype.yixiang_family_generalization_m52 import (
    audit_family_split, family_macro_average, paired_family_bootstrap
)
audit = audit_family_split(records)
if not audit.valid:
    raise RuntimeError(audit.errors)
```

## 证据边界

M52 只实现评估协议和统计原语，不包含新的 SCM 生成器，不运行真实模型，不产生任何类象优于 Transformer 的经验结论。Bootstrap 区间在家族数量很少时会很不稳定；需要增加独立家族数，而不是仅增加同一家族的 episode 数。训练/验证/测试划分应在模型调参前冻结，测试集不得用于提示词或策略迭代。
