# Storyboard and video prompt reference

Use the approved `shared-brief.md`, shot manifest, and stabilized source images to fill these templates. The examples are structural, not copy to paste defaults: preserve the project's actual ratio, duration, style, audio, reference roles, and review mode. Keep project or product specific wording in the project brief.

## User-facing creative checkpoints

```text
先判断用户要故事演绎、产品展示，还是两者结合；不确定时用一句话询问。
根据真实产品信息给出一套推荐设计。每张只突出一个主卖点；多卖点冲突时提出优先级建议，让用户决定取舍。
对每张图用四句短话说明四格分别拍什么，逐张确认。连续视频先用一句话说明整支内容如何推进。
确认用户看得懂的场景、动作、卖点和结果；不要展示技术参数。
```

Keep technical syntax out of the short conversational summary, but link the complete saved prompt file for inspection before staged approval. Default delivery is the storyboard plus its matching video prompt; after the storyboard is approved as usable, prepare the video prompt automatically. “直接生成 / 跳过流程 / 无需审核 / 只生成就行” selects fast review but does not remove the video prompt unless the user explicitly says they do not want it.

For a new multi-shot staged project, the coordinator binds each shown initial creative design using `prepare-design-review` and `approve-design`, then completes every initial full prompt and matching shot fields before concurrency choice. Keep the approved core descriptions verbatim when extending them into the technical prompt. Copy context, main selling point, purpose, four beats and scales to the matching structured shot fields; see [schema.md](schema.md). After the actual design and cross-shot review, record each initial `check-prompt-plan` before handing prompts to shot conversations. Later local revisions are checked by the responsible shot conversation. Fast mode still performs its internal check, without adding user checkpoints; legacy unmarked multi-shot projects keep their existing division of work.

## Per-shot staged review

分阶段模式先展示本镜头实际使用的原始参考图，再展示对应的技术提示词审核。新多张分阶段项目的初版完整提示词已由总控写好并核对；子对话取得真实登记身份后运行 `prepare-prompt-review`，在自己的对话中展示命令生成的简明方案，并用绝对路径链接提供现有 `storyboard-prompt.md`，不得因为接手而重新起稿。完整提示词须包含简明方案的全部核心内容，技术细节只作延展。等用户对当前镜头当前版本明确确认后，该子对话继续生成、QA、标注、图片审核、视频提示词和交付。无标记旧多张项目仍由总控核对并提交提示词审核；单张仍在当前对话。明确要求快速模式时合并审核。

```markdown
## 参考图预览

![image-01 原始参考图](/absolute/project/path/sources/image-01.jpg)

`image-01`：产品身份、结构

![image-03 原始参考图](/absolute/project/path/sources/image-03.jpg)

`image-03`：手部动作、构图

## 待确认的本镜头方案

<prepare-prompt-review 生成的视觉风格、核心卖点和四格内容>

[完整生成提示词](/absolute/project/path/shots/shot-01/storyboard-prompt.md)

请确认这张图的当前方案与完整提示词，或指出需要修改的地方。
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

【内容职责与摄影风格】
本张分镜用于【已确认的使用情境或展示情境】，重点表现【已确认的主卖点】，承担【本张在整批内容中的作用】。按已确认的风格、场景、光线与产品约束拍摄。四格使用【已确认的景别安排】，景别变化服务于动作或信息，不机械套用固定远近顺序。避免重复其他分镜的【已分配给其他分镜的开头、动作或结尾】。

【四格内容】
左上：【第1格已确认的具体画面、景别和可见状态】。标签：“【第1段时间与名称】”
右上：【第2格已确认的具体画面、景别和新增动作或信息】。标签：“【第2段时间与名称】”
左下：【第3格已确认的具体画面、景别和新增动作或信息】。标签：“【第3段时间与名称】”
右下：【第4格已确认的具体画面、景别与最终状态】。标签：“【第4段时间与名称】”
故事型分镜保持可理解的进展；展示型分镜可以用不同细节或视角组合，不强加人物故事。首尾相似只用于有明确目的且状态可见变化的呼应。

【标签样式】
每格底部居中放置一个小型奶油色圆角矩形标签，使用清晰的黑色中文字体。标签宽度适配文字，四格字号、内边距和位置保持一致，与画面底边留出安全距离，不遮挡产品重点。

【输出要求】
输出一张高清四宫格分镜图，总时长标注为4秒。四格中的产品外观与场景保持一致。不添加水印、无关文字、虚构标志或营销卖点，不改变原有图案，不出现畸形手指或错误机械结构。
```

Before presenting, replace placeholder values and remove drafting notes; keep the section headings such as `【版式】` and `【产品还原】`. Fill in the actual image IDs. Verify the product can physically perform the stated actions, the four scenes form a coherent sequence with specified cuts where needed, and the final panel matches the intended ending. For durations other than 4 seconds, recalculate every label and the output duration together. The skill's approved project settings take precedence over this template's example style and duration.

## Optional fast per-shot review package

Use this compact order only after recording the user's explicit fast-mode request in `shot.json`:

Before displaying the package, enter `review_pending` to record its artifact review ID. Use that ID and the subsequent actual user confirmation when approving. After a requested video-only edit, save the text and run `prepare-artifact-review` before displaying the revised package; retain the image and do not generate it again. IDs are internal bookkeeping, not user-facing technical questions.

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

QA：<pass / pass_with_notes；如有轻微问题，写明备注>
视频提示词：<complete prompt>
```

严重 QA 问题不进入可批准的快速审核包；记录为失败并等待用户决定，不自动重做图片。

## Video prompt

In staged mode, write this only after the storyboard has been approved. In explicitly requested fast mode, draft it for the combined review package and mark the storyboard and prompt as pending review until the user approves; do not describe the image as approved prematurely. `@Image1` is the corresponding storyboard, not an exact first frame; map original references to the actual upload order starting at `@Image2`. Product identity and structure come from the original product reference when the storyboard has minor detail drift. A severe storyboard error must be resolved before using it as video guidance.

```text
生成一条 [画幅]、[分辨率]、[时长] 的产品视频，内容为 [一句话概括本镜头主体与动作]。
镜头组织：[连续动作或剪辑序列；按本镜头四宫格画面顺序选择。剪辑序列写明切点，连续动作说明可衔接的运动。]

@Image1 是本镜头对应的四宫格分镜图，用于动作、构图和节奏参考，不是精确首帧。按左上、右上、左下、右下理解四个阶段；忽略分隔线、标签、时间码和说明文字，不将它们拍入视频。
@Image2：[原始参考图的单一或少量职责，例如产品身份、结构和数量。]
[@Image3：其他原始参考图的职责；没有则删除。]

场景与质感：[本镜头采用的场景、光线、色彩、景深和材质要求。]
[时间段1]：[起始画面、主体位置、动作和机位。]
[时间段2]：[动作推进、主体变化和运镜方向。]
[时间段3]：[重点细节、动作或对焦变化。]
[时间段4]：[最终状态、构图和镜头停稳方式。]
运镜：[连贯、可执行的镜头路径；若固定机位则明确说明。]

保持：[产品身份和数量、几何结构、材质、颜色与纹样、包装版式、手部、背景光线和最终状态中与本镜头有关的项目。] 连续动作保持运动与机位衔接；剪辑序列在指定切点换视角，保持产品身份、道具和光线一致。只让上述明确指定的元素运动。
禁止：[镜头特有错误。] 避免闪烁、形变、复制部件、图案漂移、异常手指、字幕和水印。包装小字按原图视觉版式处理，不凭空增加营销文字。
声音：[已确认的音频规则]。
```

Before presenting, remove all placeholders, reconcile the four beats and final state with the matching storyboard (approved in staged mode, still pending package review in fast mode), and verify reference numbering against the actual uploaded images. Time ranges guide order and pacing; they do not promise frame-accurate alignment. If duration changes, recalculate all four ranges and keep the project duration consistent in storyboard, labels, shot manifest, and video prompt.
