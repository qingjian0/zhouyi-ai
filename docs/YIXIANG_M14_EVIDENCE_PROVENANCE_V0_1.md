# M14 文本见证谱系与类象主张证据审计 v0.1

## 1. 研究问题

M13 已把跨域迁移限制为角色、关系、机制和条件的范围内结构对应，但不能判断引用内容是否真的支持主张。M14 分开建模文本见证、转录/引文活动、证据片段、类象主张与人工审查，并检测转引依赖、共享祖先、循环谱系、冲突和未审查证据。

## 2. 方法依据与古籍边界

古籍不是脱离传承过程的单一字符串。传世本、出土写本、类书引文、注疏、辑佚本、现代点校本与数字转录具有不同证据地位。文本差异不能先被压成一个“标准版本”，后世引文也不能回填成早期原文。

M14 的来源建模参考 W3C PROV-O 对实体、活动、责任主体、派生、引用和修订关系的区分；文本学方法参考早期中国文本版本传承研究。二者只提供来源描述与方法框架，不是古籍真实性认证器。清以前文献仍为主体；清以后用于校勘、辑佚、版本流变和解释史补漏。

## 3. 数据模型

Witness 记录作品、具体见证、卷篇/页叶定位、文本核验状态、可追溯引用、父见证、派生类型和谱系完整性声明。ClaimEvidence 将证据绑定到一个主张和一个见证，并记录支持/反驳/限定立场、审查状态、审查者与理由。

派生类型包括 copied_from、quoted_from、revised_from、transcribed_from、ocr_from、collation_of、unknown_derivation。每条父边必须声明类型。

## 4. 谱系审计与独立性

- 父见证必须存在；拒绝自环和有向环。
- 共享祖先意味着不能把两个派生见证简单计作两份独立证据。
- 只有两侧谱系均声明完整、且没有祖先或共同祖先关系时，才输出独立支持组候选。
- 这只表示“在已声明谱系下未发现依赖”，不证明历史上绝对独立；未知抄本、共同祖本未识别、横向借用和合校污染仍可能存在。

## 5. 证据裁决

- SUPPORT_ONLY：目前已审查证据中有支持、无已审查反驳；不代表主张已证明。
- CONFLICTED：支持与反驳并存，保留争议。
- QUALIFICATION_ONLY：目前仅有范围限定证据。
- INSUFFICIENT：没有已审查支持，包括仅反驳或无证据。
- UNREVIEWED：有相关证据，但全部未审查/争议。

不计算真理分数，不自动把多个引用计作独立支持；semantic_truth_established 永远为 false。

## 6. 专项测试

25 项测试覆盖根见证、派生链、缺失父节点、循环、自环、重复 ID、派生边类型、共享祖先、独立根、谱系不完整、独立支持门槛、共同祖本、证据冲突、限定证据、仅反驳、未审查、无证据、未知见证、理由不足、审查者声明违规、重复证据 ID、语义真实性边界和主张隔离。

## 7. 当前限制

1. 只审计调用方提供的谱系，不自动发现未声明的中间版本或共同祖本。
2. 不校验 URL、馆藏号、影像文件是否真实可访问；不验证图像与转录逐字一致。
3. 不判断引文语义是否蕴含类象主张；stance/rationale 由人工或上游审查提供。
4. reviewer ID 不等于审查者真实独立；不做身份认证或一致性测量。
5. 独立支持组只是谱系结构候选，不是真实独立性结论。
6. 不重建复杂分叉、污染、合校、横向借用的完整 stemma；后续需支持多亲本和不确定谱系边。

## 8. 参考资料

- W3C PROV-O: https://www.w3.org/TR/prov-o/
- Chinese Text Project scanned source texts: https://ctext.org/introduction/ens
- Martin Kern, Methodological Reflections on the Analysis of Textual Variants and the Modes of Manuscript Production in Early China: https://mkern.scholar.princeton.edu/sites/g/files/toruqf2716/files/mkern/files/methodology.pdf
- Handbook of Stemmatology: https://www.degruyterbrill.com/document/doi/10.1515/9783110684384/html

现代研究仅补充方法论，不取代古籍原典和版本学判断。
