# 可学习类象文本闭环 v1

## 本次新增能力

新增三个可组合模块：

- \`prototype/classiang_learning.py\`：从人工审阅的原始文本跨度学习特征标签提议器；支持中文单字/英文词的轻量 span 特征、负例拒绝、精确证据跨度、模型检查点和精确跨度 P/R/F1。
- \`prototype/classiang_learning_workflow.py\`：分组隔离训练/验证、跨领域留一域评估、审阅反馈重新训练，以及将文本预测 Observation 接入现有 \`run_classiang_cycle\`。
- \`prototype/classiang_multimodal.py\`：图像区域适配协议，将外部视觉提供方的区域标签绑定到图像 SHA-256 和归一化 xyxy 坐标。

不引入第三方依赖，CPU 可运行。

## 文本训练数据

UTF-8 JSON：

\`\`\`json
{
  "schema_version": 1,
  "examples": [
    {
      "observation_id": "obs-001",
      "subject_id": "pump-001",
      "domain": "mechanical",
      "source_id": "licensed-doc-001",
      "group_id": "source-family-001",
      "text": "A pump transfers water through a pipe.",
      "context": ["maintenance", "description"],
      "annotations": [
        {
          "start_char": 7,
          "end_char": 22,
          "dimension": "function",
          "value": "transfers-water",
          "purposes": ["recognition", "diagnosis"]
        }
      ]
    }
  ]
}
\`\`\`

跨度是 Python Unicode code-point 半开区间。可选字段 `negative_annotations` 用于记录经人工审阅确认的负例跨度，例如 `{"start_char": 31, "end_char": 42}`；负例不得与正例重叠。未标注文本默认是未知，不等于负例。每条标注必须精确对应原文；\`dimension\` 必须属于现有八类取象维度。至少需要两个独立 group，推荐按来源族、对象族或事件族分组，不能把同源段落拆到训练和验证两侧。

## 训练与部署

\`\`\`bash
python -m prototype.classiang_learning DATASET.json \
  --checkpoint artifacts/classiang-text.json \
  --report artifacts/classiang-text-report.json \
  --seed 17 --validation-fraction 0.2
\`\`\`

程序输出可校验 SHA-256 的 JSON 检查点及报告。推理示例：

\`\`\`python
from prototype.classiang_learning import TrainableTextEncoder

model = TrainableTextEncoder.load("artifacts/classiang-text.json")
observation = model.predict(
    observation_id="query-1",
    subject_id="pump-9",
    domain="mechanical",
    source_id="manual-9",
    text="The pump transfers water through a pipe.",
)
\`\`\`

将返回的 Observation 传给 \`prototype.classiang_pipeline.run_classiang_cycle\`，即可复用已有立类、验类、比类、推类和反例修类门控；也可用 \`run_text_classiang_cycle\` 包装这一过程。

## 反馈学习

\`append_reviewed_feedback\` 将人工审核事件追加到 JSONL。事件必须包含唯一 event_id、reviewer_id、decision（accept/correct/reject）和完整 record。reject 必须是空 annotations 的显式负例。用 \`train_deploy_workflow(..., feedback_path=...)\` 将审核后的样本加入训练集，重新训练并生成新检查点；旧检查点不被覆盖，除非调用方指定相同输出路径。

## 跨域评估

工作流提供按 domain 留一域评估；训练/验证主报告则按 group_id 隔离。报告记录各域 P/R/F1、exact-record-match、训练/验证 group、数据与模型摘要。若领域数量不足或训练折没有正标注，会明确标记 not_run，不伪造结果。

## 多模态边界

\`classiang_multimodal.py\` 只定义外部视觉模型结果的证据保真适配器。它验证图像 SHA-256、region ID、归一化坐标、特征维度和值，并把图像区域证据绑定到 Observation。它**不读取像素、不做 OCR、不执行视觉识别**。真正的图像感知必须由可替换的外部视觉/OCR provider 提供，并在独立 Gold 数据上评估。

## 重要限制

- 当前文本模型是监督式多项式朴素贝叶斯跨度提议基线，不是大语言模型或通用语义理解器。
- 它只能提出训练集中见过的 \`dimension=value\` 标签；未知概念应通过阈值弃权，不会凭空创造新本体。
- purpose_scores 是训练标注频率，不是校准概率；不得解释为真理或因果置信度。
- 现有 Naive Bayes 基线仍使用未标注候选作为弱负例，存在标注遗漏污染风险；新对比学习器只使用显式审阅的 `negative_annotations`，未标注跨度一律视为未知。
- 图像适配器不是图像编码器。音频、视频也尚未实现原生感知。
- 通过单测或合成数据只能验证工程协议。真实跨域能力必须用许可清晰、独立标注、来源族隔离的 Gold 集评估。
