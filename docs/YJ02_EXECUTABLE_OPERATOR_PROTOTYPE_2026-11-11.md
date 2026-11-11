# YJ-02：可执行算子原型与验收记录

状态：第一版确定性参考实现已提交；尚未训练，也没有 CI 结果或性能结论。  
上游：YJ-01 / PR #203。  
实现范围：YY、WX、YAO、BIAN（受限 bit-flip baseline）、SHIWEI、XIANG 六类算子。

## 文件

- `prototype/yijing_operators.py`：类型化数据契约、结果状态、六类参考算子和注册表。
- `prototype/yijing_operator_registry.json`：机器可读注册表，记录输入输出、前置条件、语义边界。
- `tests/test_yijing_operators.py`：13 个单元测试，覆盖证据缺失、上下文缺失、方向性、版本、结构映射冲突和受限状态转移。

## 重要边界

1. Yin-yang 的数值只在任务定义的轴上有效，互补性不能从数值相反自动推出。
2. Wuxing 作用边必须由调用方显式提供方向、关系类型、条件和解释版本。代码不内置某一流派的固定生克表。
3. Yao operator 只做有序位置和角色绑定，不直接给出吉凶或传统断语。
4. Bian operator 当前只有明确标记的 bit-flip baseline，不能代表完整卦变理论。
5. Shiwei 不推断历法、周期或天时规律；需要调用方显式提供上下文。
6. Xiang mapping 只检查部分结构保持；目标域证据必须独立提供，不转移源域事实。
7. 所有算子保留 NEED_CONTEXT / NEED_EVIDENCE / NOT_APPLICABLE / UNKNOWN 等状态，禁止缺证据时伪造确定答案。

## 本轮验收目标

- 每个算子都有类型化输入和显式结果状态；
- 解释版本和证据来源可追踪；
- 错误输入被拒绝或显式返回状态；
- 算子语义保持分离，不被一个通用正负边替代；
- 注册表可供后续 N0.7 registry adapter 读取。

## 尚未完成

- 真实 N0.7 operator registry adapter；
- SROK-0 多分支组合接入；
- 从数据学习算子选择/参数；
- 多 seed、机制 OOD、错误先验和反向先验实验；
- 独立 evaluator 和 CI 运行结果。

因此本次交付只能称为「确定性参考原型」，不能称为完成理论融合、完成训练或优于其他架构。
