# E12-A9：Evaluator Verdict → Epistemic Evidence Bridge

日期：2026-11-11  
状态：证据绑定与聚合原型；不是生产级可信评估服务。

## 1. 研究问题

E12-A8 把 learner 预测提交与 evaluator 评分拆开，但单次评分不足以证明候选原语已学会。E12-A7 生命周期又需要按 scope 管理证据。E12-A9 连接两者，防止“单次答对 = 已经学会”的证据膨胀。

## 2. 证据链

1. Learner 产生不可变 PredictionCommit。
2. EvaluatorVerdict 必须绑定同一 episode_id 和 commit_digest。
3. Coordinator 将候选版本与 scope 绑定到提交；该上下文不得由 learner 自己声明。
4. bind_verdict 检查预测、gold、correct 标志之间的一致性。
5. aggregate_evidence 只允许一个 candidate version、一个 scope，拒绝重复 commit。
6. 使用 Wilson 95% lower confidence bound，避免小样本全对就被判为支持。
7. append_evidence 将聚合结果写入 E12-A7 事件账本，但不自动推进 workflow stage。

## 3. 默认证据判定

- 最少样本数：30；
- Wilson 95% lower bound：至少 0.80；
- 当前确定性合成 benchmark 中，任意已评分反例标记 CONTRADICTED；
- 其他情况标记 UNDERDETERMINED。

这不是通用统计政策。若观测存在噪声、标签误差或 covariate shift，单个错误不应直接证明机制被推翻；应采用噪声模型、分层 scope、测量误差审计和反例分类。

## 4. 生命周期集成边界

只追加 EPISTEMIC_ASSESSMENT 事件：
- 不自动推进到 GATE_VALIDATED 或 REUSED；
- 不自动修改 scope status；
- 不把一个 scope 的表现迁移到其他 scope；
- 不把 evaluator 自己生成的说明文字当作独立证据。

## 5. 安全与真实性限制

当前 EvaluatorVerdict 是普通 Python dataclass，SHA-256 绑定预测提交，但 verdict 本身没有数字签名。该 bridge 能检测常见字段错配和错误标记，不能抵御能伪造 evaluator 对象的恶意调用方。

生产部署需由 evaluator 服务签名 verdict（例如 Ed25519），learner/coordinator 不得持有签名私钥；还需单调评估序号、重放保护、评估器身份/版本、数据集版本、split ID、measurement protocol、scope 定义摘要及审计日志。

## 6. 下一步

- evaluator 独立服务与签名 verdict；
- 数据集版本与 scope manifest 的密码学绑定；
- 多测量协议、噪声反例分类与 shift 检测；
- A2 主动测量请求作为独立证据事件，learner 不得自行给测量结果背书；
- 稀疏组合候选 lineage 与 evidence batch 绑定；
- 标签、verdict、scope、candidate lineage mutation 的端到端非干扰测试。

## 7. 结论

E12-A9 建立从不可变预测提交到 scope-specific 统计证据，再到认知生命周期事件的最小闭环。它降低单样本过拟合与跨 scope 证据污染风险，但仍需独立签名 evaluator 才能建立可验证信任根。
