# Classical yixiang concept map v0.1 — source-grounded research notes

Status: research map only. These passages are discovery references, not admitted gold records. Their exact wording must be checked against a scan-backed witness before annotation.

## 1. Foundational textual propositions

### 1.1 Analogy and representational form

《系辞上》:
> 圣人有以见天下之赜而拟诸其形容象其物宜，是故谓之象。

This passage gives a textual basis for treating 象 as a representational operation: an observed or conceived pattern is拟 to form/appearance and its fitting relations. It does not by itself specify a modern algorithm or prove that every later 易学类比 is valid.

### 1.2 Observation and category formation

《系辞下》:
> 古者包牺氏之王天下也，仰则观象于天，俯则观法于地，观鸟兽之文与地之宜，近取诸身，远取诸物，于是始作八卦，以通神明之德，以类万物之情。

Research decomposition:
- Observation domains: 天、地、鸟兽、地宜、身、物.
- Sampling scale: 近取诸身 / 远取诸物.
- Representation: 始作八卦.
- Intended semantic operation: 通神明之德 / 类万物之情.

The “包牺氏” origin narrative is a received textual account, not independently verified prehistorical evidence. The model should represent it as a claim made by the text, not as an established historical event.

### 1.3 Symbol, likeness, and dynamic change

《系辞下》:
> 是故易者象也，象也者像也。

《系辞上》:
> 圣人设卦观象，系辞焉而明吉凶。

《系辞上》 also states:
> 圣人有以见天下之动而观其会通以行其典礼，系辞焉以断其吉凶，是故谓之爻。

These passages support separating at least three tasks:
1. Forming/recognizing an image or symbolic pattern.
2. Observing change and its convergence/communication (会通).
3. Expressing judgments through text and action-oriented rules.

The terms 象、像、爻、辞 are related but not interchangeable.

### 1.4 Relational configuration

《说卦传》:
> 天地定位，山泽通气，雷风相薄，水火不相射，八卦相错。

This is a configuration of paired relations, not merely a list of eight independent objects. It is a natural source for testing relational and higher-order structure. The exact interpretive meaning of each relation must be annotated separately from the line itself.

## 2. A worked example: 咸卦《象传》

Received text:
> 象曰山上有泽咸君子以虚受人。

Wang Bi commentary:
> 以虚受人物乃感应。

The annotation must keep these as separate layers:
- 《象传》: a normative analogy/application (“君子以…”), not an explicit causal equation.
- 王弼注: a later explanatory gloss that interprets receptive emptiness as a condition for 感应.
- Modern punctuation, OCR, and simplified/traditional conversion: editorial/digital transformations.

Do not train on the commentary as though it were the original canonical statement. Do not label the 《象传》 line as a causal mechanism merely because the later commentary supplies a mechanism-like explanation.

## 3. Proposed claim taxonomy for annotation

| Claim class | What it records | What it must not be confused with |
|---|---|---|
| representational | 象/像 as likeness, form, or symbolic representation | modern vector embeddings |
| observational | a textual account of observing 天地、鸟兽、身、物 | verified historical field observation |
| relational | correspondence, opposition, interaction, or configuration among images | causal effect without intervention evidence |
| dynamic | change, movement, transformation, timing, and sequence | static similarity |
| normative analogy | “君子以…” applications from an image to conduct | empirical causal law |
| divinatory | relation between signs, judgment, and future-oriented interpretation | ordinary prediction benchmark accuracy |
| commentarial | later explanations that reinterpret, extend, or systematize earlier lines | canonical source wording |

Every claim should retain:
- source layer and attribution status;
- witness ID, edition, locator, and exact character offsets;
- claim class and confidence;
- alternative readings and variants;
- counterexamples or conflicting commentarial interpretations;
- annotation/adjudication state.

## 4. Implications for Zhouyi-AI architecture

1. **Source segmentation before reasoning:** split canonical text, Ten Wings, commentaries, glosses, and modern editorial notes before extracting concepts.
2. **Entity-role extraction before analogy:** identify the image entities, properties, relations, and target domain instead of matching whole phrases by surface similarity.
3. **Relational alignment:** use M57/M58 only as controlled graph-reasoning diagnostics until text-grounded annotations exist.
4. **Evidence-carrying claims:** every inferred mapping must point to exact witness spans and disclose whether it is explicit, analogical, commentarial, or hypothetical.
5. **Causal restraint:** a structural analogy is not automatically a causal claim. M60/M61 intervention tests are a separate validation layer.
6. **Historical restraint:** traditional attribution and narrative dating are recorded as claims with uncertainty, not silently converted into facts.

## 5. Source discovery references

- 《周易》四部丛刊本卷七（系辞上，景上海涵芬楼藏宋刊本）: https://zh.wikisource.org/zh-hans/周易_(四部丛刊本)/卷七
- 《周易》四部丛刊本卷四（咸卦，景上海涵芬楼藏宋刊本）: https://zh.wikisource.org/zh-hans/周易_(四部丛刊本)/卷四
- 《周易》四部丛刊本卷八（系辞下）: https://zh.wikisource.org/zh-hans/周易_(四部丛刊本)/卷八
- 《周易》四部丛刊本卷九（说卦传）: https://zh.wikisource.org/zh-hans/周易_(四部丛刊本)/卷九
- 《周易正义》系辞下卷八之二（孔颖达疏; commentary layer): https://zh.wikisource.org/zh-hans/周易正义/08.2
- 《原本周易本义》四库全书本卷八（朱熹注; Qing witness): https://zh.wikisource.org/zh-hans/原本周易本义_(四库全书本)/卷08

These are digital discovery links. The CText catalog identifies the Four Books Congkan 《周易》 as a facsimile of a Song printed edition, while the text platform warns that its text is OCR-matched to the base edition. The source remains discovery-only until scan inspection and transcription verification.
