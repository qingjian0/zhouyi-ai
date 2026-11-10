# 相关工作与文献记录

> 文献表是研究入口，不是完整系统综述。引用前应核对论文正式版本、作者、年份、会议/期刊和代码许可证。下列条目用于定位研究脉络，不能据此宣称 CPG-EI 已被验证。

## 1. 离散扩散与非自回归语言模型

- Yixuan Li et al., [*An overview of discrete diffusion models in natural language processing*](https://doi.org/10.1007/s44336-026-00040-5)（Vicinagearth，2026-09-30）。离散扩散语言建模综述，涉及迭代去噪、双向上下文和并行生成。需要重点比较训练目标、解码策略、质量-延迟权衡。
- Jinbin Bai et al., [*PRISM: Efficient Test-Time Scaling via Hierarchical Search and Self-Verification for Discrete Diffusion Language Models*](https://proceedings.mlr.press/v306/bai26f.html)（ICML 2026）。层级搜索与自验证，说明扩散模型的测试时搜索也在向多路径推理发展。
- Longxuan Yu et al., [*DSL-LLaDA: Scaling Continuous Denoising to 8B Masked Diffusion LMs*](https://aclanthology.org/2026.findings-emnlp.2101/)（EMNLP Findings 2026）。连续嵌入去噪与多位置联合演化。
- *Diffusion LLMs Can Do Faster-Than-AR Inference via Discrete Diffusion Forcing*（ICLR 2026）。块级与跨块并行推断。
- *Why Diffusion Language Models Struggle with Truly Parallel (Non-Autoregressive) Decoding?*。关注实际解码是否仍表现出自回归倾向。

**对本项目的影响：** 并行生成、双向上下文和多候选搜索均不是新颖性来源。CPG-EI 必须把创新问题收敛到动态语义组合、高阶关系结构、自组织机制及易象先验是否产生可测增益。

## 2. 超图与高阶关系学习

- Sunwoo Kim et al., [*A Survey on Hypergraph Neural Networks: An In-Depth and Step-By-Step Guide*](https://doi.org/10.1145/3637528.3671457)（KDD 2024）。超图神经网络综述。
- *Recent Advances in Hypergraph Neural Networks*（2025）。讨论模型类别、复杂度与过平滑等问题。
- *Beyond Graphs: Can Large Language Models Comprehend Hypergraphs?*（ICLR 2025）。提出高阶结构理解评测问题。

**对本项目的影响：** 使用超图本身不是创新。需证明动态超边选择和语义角色建模相对普通图、静态超图带来增益，同时报告复杂度。

## 3. 易象与神经网络的已有研究

- Bowen Wang et al., [*Multi-reservoir echo state network based on the I Ching for accurate energy prediction*](https://doi.org/10.1016/j.engappai.2025.113307)（Engineering Applications of Artificial Intelligence，2026-01-15）。研究将太极、五行、八卦相关结构用于多储备池网络的组织与预测。

**对本项目的影响：** 不能宣称首次将《周易》引入神经网络。CPG-EI 的差异假设应聚焦动态超图组合、非 Token 中心语义计算、证据约束的类象迁移与自组织更新的统一机制。

## 4. 认知科学与组合性

- *Concepts and Compositionality: In Search of the Brain's Language of Thought*。概念组合与思想语言假设的认知科学讨论。
- *Data-to-text Generation with Variational Sequential Planning*。高层规划与文本生成之间的分离，可作为结构化计划的参考。
- *Adaptive Neural Message Passing for Inductive Learning on Hypergraphs*。超图上的自适应消息传递。

## 5. 研究比较维度

| 方向 | 已有技术重点 | CPG-EI 需验证的差异 |
|---|---|---|
| Diffusion/NAR | 多位置并行生成、迭代去噪 | 是否有显式语义组合结构 |
| Graph NN | 成对关系传播 | 动态多元超边是否带来收益 |
| Hypergraph NN | 高阶关系聚合 | 超边能否由任务反馈自组织 |
| Planning/Search | 多路径搜索和验证 | 语义组合结构与证据协调的联合贡献 |
| I-Ching inspired NN | 符号结构/储备池组织 | 可学习、可拒绝的易象先验是否提升迁移 |

## 6. 待补全的文献工作

- 对每篇论文补齐 DOI/arXiv/出版社链接、作者、版本与代码仓库。
- 阅读方法章节，记录训练目标、参数规模、计算成本和基准。
- 复核 2026 年论文的正式发表状态。
- 建立引用管理文件，记录引用许可与数据许可。
