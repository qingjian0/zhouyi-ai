# E12-A8：Evaluator Firewall 与隐藏标签隔离

日期：2026-11-11  
状态：最小可运行原型；不是生产级安全隔离。

## 1. 问题定义

E12-A6 x E02-D 旧 runner 在同一函数内生成 gold，并把 Gate-Final 标签写入 learner 可见的生命周期 ledger。即使记录 prediction commit step 与 label visibility step，时间字段本身也不能证明 learner 无法读取标签。

E12-A8 将预测与评分拆开：

1. Learner subprocess 只接收公开 support observations、query 和 episode id。
2. Learner 输出冻结的 PredictionCommit，包含预测、可辨识性、候选 trace、公开输入摘要与提交摘要。
3. Coordinator 在预测提交完成后，调用 evaluator。
4. Evaluator 独占隐藏标签，输出只读 EvaluatorVerdict，并绑定 commit digest。
5. 同一 commit 不可重复评分；修改提交内容会导致摘要校验失败。

## 2. 数据流契约

    Public observations ──> Learner subprocess ──> PredictionCommit
                                                       |
    Hidden labels ──> Evaluator process <──────────────┘
                            |
                            └──> EvaluatorVerdict

禁止 learner 输入包含：generator rule、gold label、Gate-Final label、Locked-Test label、evaluator verdict、隐藏 split outcome。

## 3. 非干扰性质

给定固定公开输入 P，隐藏标签 H1、H2，应满足：

    Learner(P, H1) = Learner(P, H2)

更精确地说，learner 根本不接收 H；对两个仅在 evaluator 私有标签上不同的执行，commit 序列化结果和 digest 必须一致。Evaluator score 可以变化。

当前测试覆盖：
- 隐藏标签改变时 learner commit 不变；
- support/candidate 输入顺序改变时 canonical trace 不变；
- commit 不可变；
- commit 篡改检测；
- 同一 commit 重复评分拒绝；
- evaluator 缺少标签时拒绝评分；
- learner commit 不含 gold/label/verdict 字段。

## 4. 安全边界与明确限制

当前实现启动独立 Python 子进程，但这不构成 OS 安全沙箱：
- 子进程与父进程通常使用同一 OS 用户权限；
- 子进程仍可能读取可访问文件、环境变量、进程信息或网络资源；
- evaluator 类的私有字段只是语言级封装，不是抵御恶意代码的安全边界；
- SHA-256 digest 用于完整性绑定，不提供来源真实性或签名；
- 当前 evaluator 在协调器进程中运行，尚未独立部署为受限服务。

因此，本原型验证的是受控代码路径的数据最小化与标签非干扰，不是对任意恶意 learner 的机密性保证。

生产化下一步需要：独立容器/OS 用户、只读文件系统、禁网或受控网络、最小环境变量、资源限制、单向 IPC、评估器密钥/标签存储隔离、签名提交与审计日志。

## 5. 尚未完成

- 重构 E02-D 全部实验 runner，确保任何 learner 代码路径均不持有 gold；
- 独立 evaluator 服务与认证 IPC；
- 隐藏标签 mutation 的跨进程全 trace 对比（当前比较 commit）；
- 标签访问审计和故意越权 learner 的 OS 级阻断；
- evaluator verdict 接入 E12-A7 生命周期事件，验证 verdict 与冻结 commit 的一一绑定；
- Locked-Test 数据集和评估器部署隔离。

## 6. 结论

E12-A8 首先建立可测试的数据流契约，而不是把“进程私有变量”包装成安全保证。当前可声明：公开输入驱动的 learner 子进程会生成可校验、不可变的预测提交；隐藏标签只用于 evaluator 评分；有限 mutation tests 验证 commit 非干扰。不能声明已实现生产级安全隔离。
