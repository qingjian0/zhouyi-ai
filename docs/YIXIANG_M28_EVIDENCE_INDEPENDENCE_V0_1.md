# M28：类象证据独立性与共同来源污染审计 v0.1

## 1. 研究问题

M14 已能检测见证谱系中的共同祖先，但其 Witness 结构将作品、版本和见证混合在一个对象中，且独立性判断主要依赖已登记的父见证关系。M28 将三层身份拆开：

1. **SourceIdentity**：来源实体及其来源家族/独立性组；
2. **Witness**：某一具体版本、数字转录、影像或引文见证；
3. **Derivation**：转录、引文、OCR、翻译、注释、校勘、复制等派生活动。

不同网站、不同 URL、不同数字页面，不自动构成不同来源。相同来源家族内的镜像、重排或转载不应扩大独立支持数。

## 2. 古典文献学依据与边界

《墨子·小取》提出“以类取，以类予”，同时指出“其然也同，其所以然不必同”，并警告推类“远而失，流而离本”。M28 将此作为审查证据来源与推论根据的启发：表面上多条记录相同，不代表其形成原因彼此独立；但这只是现代证据审计映射，不能说《小取》提出了现代来源图或统计独立性理论。参见《墨子·小取》数字转录及四部丛刊本见证：https://zh.wikisource.org/zh-hans/墨子/小取 、https://zh.wikisource.org/zh-hans/墨子_(四部丛刊本)/卷第十一 。

《荀子·正名》讨论同状异所、异状同所，并要求以名实核验分类。对 M28 的启发是：作品、版本、见证、来源家族和数字记录不能因名称相似而混同，也不能因页面不同而误判为不同来源。此为现代数据建模推论，不是对原文的直接释义：https://zh.wikisource.org/zh-hans/荀子/正名篇 。

古籍数字化规程继续遵循：原始影像优先；OCR/标点/翻译作为派生层；类书引文、注疏、辑佚、现代整理分别记录；异文并存，不以模型投票强行合并。清以前材料为研究主体，清以后只用于校勘、辑佚、版本流变与解释史补漏。

## 3. 数据模型

- SourceIdentity：source_id、work_id、source_type、independence_group、description。
- Witness：witness_id、source_id、edition_id、witness_type、locator、text_layer、verification_state、lineage_complete。
- Derivation：parent_witness_id、child_witness_id、kind、certainty、note。
- EvidenceAssertion：claim_id、witness_id、stance、review_state、reviewer_ids、rationale。

派生类型明确区分 transcription、quotation、paraphrase、commentary、collation、OCR、translation、copy、revision、unknown。

## 4. 独立性判定

仅当两条已审查支持记录满足以下条件，才登记为“声明谱系下的独立支持对”：

1. 两个见证谱系均声明完整；
2. 两见证不存在祖先/后代关系；
3. 两者不存在已登记共同祖先；
4. 两者 SourceIdentity 不同；
5. 两来源的 independence_group 不同。

这是一项保守门槛。独立支持对不等于历史上绝对独立；未识别共同祖本、横向借用、合校污染、失传中介本及来源家族划分错误仍可能存在。来源家族字段由研究者登记，系统不自动推断。

## 5. 冲突与证据数量

支持、反驳、限定和未审查记录分别保留。反驳不会删除支持；新版本不会覆盖旧见证；未审查或争议记录不计入已审查支持。输出同时保留记录数、见证数、来源身份数、来源家族和独立支持对，禁止把转载记录数当成独立证据数。

## 6. 与 M27 的集成边界

M28 当前提供独立的谱系审计 API，不直接修改 M27 的 ClaimNode 或 RevisionEvent。未来适配器应先由 M28 将被撤销根见证展开为受影响 witness/evidence ID 集，再显式映射到 M27 的 revoked_evidence_refs。不得把 M28 的 witness_id、source_id 与 M27 的任意 evidence_ref 按字段名自动等同。

## 7. 测试覆盖

25 项专项测试覆盖：独立来源组、同源多数字见证、同家族多版本、共同祖先、祖先/后代、OCR/翻译派生、谱系不完整、冲突/限定/未审查并存、循环、悬空端点、自环、重复 ID、未知来源、主张隔离及语义蕴含边界。

## 8. 当前限制

- 不认证文献真伪、版本年代或影像真实性；
- 不自动发现未登记共同祖本或隐性转引；
- 不自动判断某段文字是否支持主张；
- 不验证审查者现实身份与独立性；
- independence_group 是人工声明，不是算法发现的谱系事实；
- 不把“两个根节点”解释成“两个独立来源”；
- 不声称证据独立性等同于证据充分性或理论有效性。
