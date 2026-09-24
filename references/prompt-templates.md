# Storyboard and video prompt reference

Use the approved `shared-brief.md`, shot manifest, and stabilized source images to fill these templates. The examples are structural, not copy to paste defaults: preserve the project's actual ratio, duration, style, audio, reference roles, and review mode. Keep project or product specific wording in the project brief.

## Compact global confirmation

```text
画幅 / 布局 / 时长：9:16 / 2x2 / 默认4秒
时长规则：每镜头不少于4秒；大部分为4–10秒；四格时间按已确认时长派生
视觉与声音：<shared style, continuity, audio>
审核方式：分阶段确认提示词与分镜图；需要视频提示词时再确认；明确要求快速模式时合并审核
数量与执行：未指定数量默认1张；单张在当前对话确认与制作；多张且需要创建并发任务时，再询问“全部开始”或“先做1–2个看效果”
交付：默认带标签分镜图；用户要求时增加视频提示词；不自动生成付费视频
模式判定：普通“生成/批量生成/生成分镜图”仍为分阶段审核；只有用户明确要求直接生成、跳过确认或合并审核时才使用快速模式

镜头映射：<shot -> images and narrow roles>
```

## Per-shot staged review

分阶段模式先直接嵌入本镜头实际使用的原始参考图，每张图后紧跟“图片编号 → 本镜头职责”，随后提交完整分镜生成提示词并等待确认。默认不得为了预览另行生成或拼合图片。提示词获批后才生成、QA、标注并提交分镜图。仅在组合交付时，分镜获批后再提交视频提示词。明确要求快速模式时合并审核。

```markdown
## 参考图预览

![image-01 原始参考图](/absolute/project/path/sources/image-01.jpg)

`image-01`：产品身份、结构

![image-03 原始参考图](/absolute/project/path/sources/image-03.jpg)

`image-03`：手部动作、构图

## 分镜生成提示词

<complete prompt>

请确认，或说明需要如何修改。确认前不会生成分镜图。
```

## Storyboard image generation prompt

Use the following Chinese prompt as the standard starting point for each product storyboard. Replace the reference IDs, product-specific actions, and any project-approved settings before presenting it. The 4-second labels below are this template's preset; if the project has already approved another duration, preserve that duration and recalculate all four ranges. A format reference is optional: only claim one was provided when an actual format image exists. Keep product reference and format reference roles distinct. The final deliverable includes the labels specified below; the image-generation workflow may add them deterministically after generating clean panels.

```text
请根据我上传的产品照片，生成一张用于视频制作的四宫格产品分镜图。【如确实上传了分镜格式图：严格参考我提供的分镜格式图。】

【参考图职责】
【产品照片编号】：主体外观的唯一依据，重点还原【产品身份、结构、数量、配件等本镜头所需内容】。
【分镜格式图编号；未提供则删除】：只参考排版、摄影风格和标签样式，不采用其中的产品或装饰图案。
【其他参考图编号及单一职责；没有则删除】。

【版式】
整张图为9:16竖版，采用两行两列的四宫格布局，四格等大，每格也是9:16竖屏构图。格子之间使用细窄的奶油白色分隔线。阅读顺序为左上、右上、左下、右下。不要添加总标题或额外说明。

【产品还原】
产品照片是主体外观的唯一依据，准确保留产品的颜色、材质、比例、结构、图案及配件。格式参考图只用于参考排版、摄影风格和标签样式，不要将参考图中的产品或装饰图案混入新图。【未提供格式参考图时，删除前一句。】

【摄影风格】
写实生活方式产品摄影，温暖自然的木质桌面，柔和侧向日光，真实阴影，统一色温与曝光。产品占据画面主要区域，使用斜向摆放、俯拍和局部特写增加变化。背景简洁，少量环境道具只能位于边缘，不遮挡主体。避免插画感、塑料渲染感和过度磨皮。【如项目已确认不同场景与光线，用已确认设置替换本段。】

【四格内容】
左上：产品完整外观，展示主要造型与装饰，画面清晰完整。
标签：“0–1秒 外观展示”
右上：展示产品内部、展开状态或第二个重要展示面，突出结构与内容。
标签：“1–2秒 结构展示”
左下：展示一个真实使用动作或功能细节，可出现自然的手部操作。动作必须符合产品实际结构，不虚构功能。
标签：“2–3秒 使用细节”
右下：回到产品最有辨识度的外观，以更精致的角度展示材质和图案，作为视频结束定格。
标签：“3–4秒 产品定格”
如果产品不适合展开或手部操作，应根据真实特点改为其他角度或材质特写，并同步调整标签名称。【将各格改写为本镜头可见、连贯的具体状态；不要保留不适用的动作。】

【标签样式】
每格底部居中放置一个小型奶油色圆角矩形标签，使用清晰的黑色中文字体。标签宽度适配文字，四格字号、内边距和位置保持一致，与画面底边留出安全距离，不遮挡产品重点。

【输出要求】
输出一张高清四宫格分镜图，总时长标注为4秒。四格中的产品外观与场景保持一致。不添加水印、无关文字、虚构标志或营销卖点，不改变原有图案，不出现畸形手指或错误机械结构。
```

Before presenting, replace placeholder values and remove drafting notes; keep the section headings such as `【版式】` and `【产品还原】`. Fill in the actual image IDs. Verify the product can physically perform the stated actions, the four scenes form a coherent sequence with specified cuts where needed, and the final panel matches the intended ending. For durations other than 4 seconds, recalculate every label and the output duration together. The skill's approved project settings take precedence over this template's example style and duration.

## Optional fast per-shot review package

Use this compact order only after recording the user's explicit fast-mode request in `shot.json`:

```text
镜头：<shot-id / title>
引用职责：<image -> narrow role>
四格：
- 0–1秒：<state>
- 1–2秒：<state>
- 2–3秒：<state>
- 3–4秒：<final state>
运镜：<motion / cut / focus / stop>
保持：<critical invariants>
禁止：<critical failures>

<labeled storyboard image>

| 时间 | 图片内标签 | 完整描述 |
|---:|---|---|
| 0–1秒 | <4–8 characters> | <full state> |
| 1–2秒 | <4–8 characters> | <full state> |
| 2–3秒 | <4–8 characters> | <full state> |
| 3–4秒 | <4–8 characters> | <final state> |

QA：<pass / known minor issues / severe failure awaiting user decision>
视频提示词：<complete prompt>
```

## Video prompt

In staged mode, write this only after the storyboard has been approved. In explicitly requested fast mode, draft it for the combined review package and mark the storyboard and prompt as pending review until the user approves; do not describe the image as approved prematurely. `@Image1` is the corresponding storyboard, not an exact first frame; map original references to the actual upload order starting at `@Image2`. Product identity and structure come from the original product reference when the storyboard has minor detail drift. A severe storyboard error must be resolved before using it as video guidance.

```text
生成一条 [画幅]、[分辨率]、[时长] 的产品视频，内容为 [一句话概括本镜头主体与动作]。
镜头组织：[连续动作或剪辑序列；按已确认分镜选择。剪辑序列写明切点，连续动作说明可衔接的运动。]

@Image1 是已确认的四宫格分镜图，用于动作、构图和节奏参考，不是精确首帧。按左上、右上、左下、右下理解四个连续阶段；忽略分隔线、标签、时间码和说明文字，不将它们拍入视频。
@Image2：[原始参考图的单一或少量职责，例如产品身份、结构和数量。]
[@Image3：其他原始参考图的职责；没有则删除。]

场景与质感：[已确认的场景、光线、色彩、景深和材质要求。]
[时间段1]：[起始画面、主体位置、动作和机位。]
[时间段2]：[动作推进、主体变化和运镜方向。]
[时间段3]：[重点细节、动作或对焦变化。]
[时间段4]：[最终状态、构图和镜头停稳方式。]
运镜：[连贯、可执行的镜头路径；若固定机位则明确说明。]

保持：[产品身份和数量、几何结构、材质、颜色与纹样、包装版式、手部、背景光线和最终状态中与本镜头有关的项目。] 连续动作保持运动与机位衔接；剪辑序列在指定切点换视角，保持产品身份、道具和光线一致。只让上述明确指定的元素运动。
禁止：[镜头特有错误。] 避免闪烁、形变、复制部件、图案漂移、异常手指、字幕和水印。包装小字按原图视觉版式处理，不凭空增加营销文字。
声音：[已确认的音频规则]。
```

Before presenting, remove all placeholders, reconcile the four beats and final state with the approved storyboard, and verify reference numbering against the actual uploaded images. Time ranges guide order and pacing; they do not promise frame-accurate alignment. If duration changes, recalculate all four ranges and keep the approved duration consistent in storyboard, labels, shot manifest, and video prompt.
