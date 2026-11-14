# M46：跨模块强类型适配契约 v0.1

M46 建立 StageArtifact、AdapterContract 与 AdapterAudit，校验来源阶段、schema version、artifact/evidence/run 引用、情境一致性和运行验证状态。它把“有引用”与“已验证可用”分开。

古典参照：《荀子·正名》关于名实、同异和情境的讨论；《墨子·小取》提醒同一推类形式在不同“所以然”下不能直接照搬。工程含义是适配器必须声明版本和上下文，而不是仅凭字段同名就强行转换。

限制：这是通用引用级强类型契约，尚未把 M37–M44 每个真实 dataclass 逐一映射为自动转换器；没有端到端对象接线或运行时 schema registry。
