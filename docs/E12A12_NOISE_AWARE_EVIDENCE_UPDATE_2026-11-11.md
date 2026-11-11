# E12-A12：噪声感知的测量证据更新

日期：2026-11-11  
状态：序贯似然比原型；不是通用因果识别器。

## 研究问题

E12-A11 解决测量执行、签名和防重放；E12-A12 解决一个经验证的观测在何种模型假设下支持或削弱候选原语。观测本身不带证明/反驳标签，证据方向由预先冻结的候选假设与竞争假设的观测似然共同决定。

## 模型

对候选原语版本 C、scope S、测量协议 P，预注册：
- 候选假设下结果分布 p(y|C,S,P)
- 竞争假设下结果分布 p(y|not-C,S,P)
- 显著性错误率参数 alpha 与 beta

每个已签名观测贡献：

    delta_t = log(p(y_t|C,S,P) / p(y_t|not-C,S,P))
    L_t = sum(delta_i, i=1..t)

采用序贯概率比检验边界：

    A = log((1-beta)/alpha)
    B = log(beta/(1-alpha))

- L_t >= A：SUPPORTED
- L_t <= B：REFUTED_IN_SCOPE
- 其余：UNDERDETERMINED

单个噪声反例只贡献一个负的 log-likelihood increment，不会自动推翻原语。重复且在竞争模型下更可能出现的观测才逐渐把证据推向范围内反驳边界。

## 工程边界

- 只接受 A11 Ed25519 签名的 SELECT 回执。
- 验证 executor/key、candidate version、scope、scope digest 和 protocol ID。
- 对同一 executor/key 使用连续序号和重复回执保护。
- 似然模型在观测前冻结；模型 digest 进入证据 ID。
- 每次更新写入 A7 append-only lifecycle ledger，事件限定在单一 scope。
- 仅更新 epistemic status，不自动推进 workflow stage 或更改其他 scope。
- 竞争假设是明确的对照模型，不等于所有可能的非候选机制。

## 统计解释限制

SPRT 的错误率解释依赖模型正确、观测协议稳定、样本条件独立或其依赖结构被正确建模。若观测存在自相关、选择偏差、概念漂移、测量误差率变化或模型失配，名义 alpha/beta 不再保证实际错误率。生产版应加入分层/条件似然、过度离散模型、时间相关模型、校准集、漂移检测和稳健敏感性分析。

当前原型拒绝零概率，以避免单条观测造成无穷大证据；不允许模型对照分布不归一化。模型注册、版本冻结与独立审批尚未实现。签名证明回执由受信密钥签发，不证明测量协议或似然模型正确。

## 验证覆盖

测试包括：单个反向观测仍为 underdetermined、连续一致观测跨过支持/反驳阈值、混合观测抵消、错误 scope 拒绝、分布归一化与零概率校验、A7 scope 隔离。

## 下一阶段

E12-A13 研究模型失配与环境漂移诊断：区分候选原语失效、测量协议漂移、分布漂移、scope 越界和竞争假设不充分；诊断不确定时优先标记 SHIFT_SUSPECTED / UNDERDETERMINED，而不是 REFUTED_IN_SCOPE。
