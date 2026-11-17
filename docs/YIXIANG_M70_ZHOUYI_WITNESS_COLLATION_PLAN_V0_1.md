# M70 — 《周易注》类象关键段落的版本校勘研究设计 v0.1

Status: literature-led witness map and collation protocol. No manuscript reading, variant collation, transcription adjudication, or Gold admission is claimed.

## 1. Research question

Investigate the Wang Bi commentarial passage attached to 乾卦《文言》:

> 夫易者象也。象之所生，生于义也。有斯义，然后明之以其物。故以龙叙乾，以马明坤，随其事义而取象焉。

The Four Books Congkan scan's page 9 layout and transcription place this passage in the Wang Bi commentary layer. It must not be conflated with the received 《系辞下》 sentence “是故易者象也，象也者像也”. The two passages are related research targets, not one quotation or one textual witness.

Questions to resolve:
1. What is the earliest recoverable wording of this Wang Bi commentarial passage?
2. Which parts are present in surviving Tang Dunhuang fragments, and do those fragments actually cover this exact locus?
3. Which variants occur across Song witnesses and later printed editions?
4. Do differences change the meaning of “义—物—象—取象” or only orthography/graphic form?
5. Which statements belong to Wang Bi's commentary, received base text, later subcommentary, or modern editorial explanation?

## 2. Witness hierarchy and evidence status

| Witness / resource | Reported identity | Use in this project | Current status |
|---|---|---|---|
| Four Books Congkan facsimile, DJVU page 9/10 | Facsimile described as depicting the Shanghai Hanfenlou-held Song printed exemplar; modern facsimile, not original Song object | Main image locator for initial diplomatic transcription | Two-page visual spot-check only |
| Tang Dunhuang Wang Bi 《周易注》 fragments | Secondary literature reports 20 Wang Bi-related scrolls among 23 Dunhuang 《周易》 scrolls | Potential early manuscript witnesses, only if exact passage survives | Shelfmark inventory and locus coverage not yet established |
| National Library Fuzhou Gongshi Ku copy | Listed among witnesses collated by the 2023 critical edition | Independent Song witness / variant comparison | Bibliographic lead; scan not inspected |
| National Library Tianlu Yushu old Song copy | Listed in 2023 edition | Independent Song witness / variant comparison | Bibliographic lead; scan not inspected |
| Southern Song Jianyang edition | Listed in 2023 edition | Song witness / variant comparison | Bibliographic lead; scan not inspected |
| Southern Song eight-line annotated edition | Listed in 2023 edition | Combined base-text/commentary layout comparison | Bibliographic lead; scan not inspected |
| Yue family Xiangtai edition | Listed in 2023 edition | Later Song textual witness | Bibliographic lead; scan not inspected |
| Song edition 《周易要义》 | Listed in 2023 edition | Excerpted/derived witness; check quotation context and editorial mediation | Bibliographic lead; scan not inspected |
| Song Jiading edition 《周易集解》 | Listed in 2023 edition | Parallel quotation witness where the passage is actually cited | Bibliographic lead; scan not inspected |
| Ruan Yuan 《十三经注疏》 / 校勘记 | Qing printed collated edition | Later collation comparator, never an early witness | Secondary textual witness |
| 2023 商务印书馆 谷继明整理《周易注》 | Modern critical edition based on Four Books Congkan facsimile and collating multiple witnesses | Finding aid for variant loci and editorial decisions | Modern editorial synthesis; not a manuscript witness |

The 2023 edition's publisher description explicitly lists the Dunhuang fragments, Fuzhou copy, Tianlu Yushu Song copy, Southern Song Jianyang copy, eight-line edition, Yue edition, Song 《周易要义》, and Song Jiading 《周易集解》 among its collated materials. This is a high-value collation map, but the edition's reported variants must be traced back to the actual witnesses before admission.

## 3. Dunhuang evidence: what is known and what is not

A 2016 article abstract reports:
- 23 Dunhuang 《周易》 scrolls in total;
- 20 scrolls classified as Wang Bi 《周易注》 fragments;
- the fragments are Tang manuscripts and are described as the earliest surviving manuscript witnesses of Wang Bi's commentary;
- comparison with the Ruan Yuan printed 《周易正义》 reports ten places where the Dunhuang reading is judged superior: three omissions, five mistaken alterations, and two interpolations in the later printed comparator.

The same abstract names P.2530 and P.2532 in earlier collation history, and mentions P.2619, P.3683, and S.6162 in Wang Chongmin's catalogue notes. These are discovery leads, not a complete shelfmark inventory and not proof that any one fragment contains the “夫易者象也” passage.

**Hard gate:** do not claim a Dunhuang variant for the target passage until a specific manuscript shelfmark, image/folio, and overlapping text span are verified. If the fragment does not cover the target passage, it can inform the broader Wang Bi textual tradition but cannot be used as direct evidence for this locus.

## 4. Required collation protocol

For each witness:
1. Identify repository, shelfmark, catalogue record, physical/digital format, estimated date, and provenance.
2. Locate the exact passage; record folio/page, column/line, and a stable image URI.
3. Transcribe the visible text diplomatically, preserving original graphs, omissions, damage, and uncertain readings.
4. Mark textual layer: received base text, Wang Bi commentary, Han Kangbo commentary, Xing Shu commentary, Kong Yingda subcommentary, later editorial note, or uncertain.
5. Align only overlapping spans; do not infer missing text from another witness.
6. Classify variants: graphic/orthographic, lexical, omission, addition, transposition, segmentation, layer-boundary, or uncertain.
7. Have two annotators independently transcribe and classify; adjudicate disagreements with explicit reasons and image evidence.
8. Record the modern critical edition's adopted reading separately from the diplomatic witness readings.

Suggested record fields:
- witness_id, repository, shelfmark, witness_date, edition_lineage
- scan_uri, page_or_folio, image_region, accessed_at
- layer, text_span_start, text_span_end, diplomatic_text
- normalized_text, variant_type, variant_reading, editorial_decision
- annotator_a, annotator_b, adjudication_status, adjudication_note
- source_citation, confidence, gold_eligibility

## 5. Interpretation guardrails

Do not collapse these propositions:
- 《系辞上》 “圣人有以见天下之赜而拟诸其形容，象其物宜，是故谓之象”;
- 《系辞下》 “是故易者象也，象也者像也”;
- Wang Bi's commentarial “夫易者象也，象之所生，生于义也……” attached to 乾卦《文言》;
- Wang Bi 《周易略例·明象》 statements about image, meaning, and language;
- later Tang/Kong Yingda explanations and modern scholarly reconstructions.

The target commentary suggests a theory of taking images according to the meaning and situation of a line/hexagram. It is not itself proof of a universal algorithm, a historical account of the earliest origins of 易象, or a validation dataset. Any computational operationalization must be tested against independently annotated examples and counterexamples.

## 6. Gold admission decision

Current decision: **not admitted**.

Admission requires:
- direct image access for each cited witness;
- exact locus overlap;
- complete diplomatic transcription;
- two independent annotations and adjudication;
- accepted claim-level decisions;
- provenance metadata and stable scan URI;
- explicit separation of the base text and commentary layers.

The Four Books Congkan pages 9–10 remain discovery/review-pending. The modern critical edition and secondary literature are research aids, not substitutes for direct witness evidence.

## 7. References and research leads

- 商务印书馆, 2023, 谷继明整理《周易注》, ISBN 978-7-100-20654-9. Publisher description states that the Four Books Congkan facsimile is the base and lists the Dunhuang, Fuzhou, Tianlu Yushu, Southern Song Jianyang, eight-line, Yue, Song 《周易要义》, and Song Jiading 《周易集解》 witnesses used for collation: https://www.cp.com.cn/book/4d4efcc9-9.html
- University of International Business and Economics library catalogue for the same 2023 edition and its collation list: https://opac.uibe.edu.cn/opac/book/499b84abbc2aacae017687db82d7f176
- 赵继宁, “敦煌本王弼《周易注》札记,” 《太原理工大学学报（社会科学版）》, 2016年第5期. Its abstract reports 23 Dunhuang 《周易》 scrolls, 20 Wang Bi-related fragments, and ten reported variant loci against the Ruan Yuan edition: https://www.fx361.com/page/2016/0210/16852677.shtml
- Peking University Confucian Canon Editorial and Research Center, introduction to the critical edition, including the debate over the exact Song printing lineage of the Four Books Congkan base: https://ruzang.pku.edu.cn/rzen/info/1017/1177.htm
- Four Books Congkan DJVU index and page locators: https://zh.wikisource.org/wiki/Index:Sibu_Congkan0001-王弼-周易-2-1.djvu
- Page 9 transcription: https://zh.wikisource.org/wiki/Page:Sibu_Congkan0001-王弼-周易-2-1.djvu/9
- Page 10 transcription: https://zh.wikisource.org/wiki/Page:Sibu_Congkan0001-王弼-周易-2-1.djvu/10
