# Storyboard and video prompt reference

Use the approved `shared-brief.md`, shot manifest, and stabilized source images to fill these templates. The examples are structural, not copy to paste defaults: preserve the project's actual ratio, duration, style, audio, reference roles, and review mode. Keep project or product specific wording in the project brief.

## Photography and lighting defaults

Unless the user specifies another style, a designated style/light reference provides it, or a different style is already approved, use realistic smartphone photography: natural detail, material and depth of field, without artificial plastic-like rendering, excessive smoothing, exaggerated blur or gratuitous cinematic treatment. Preserve the product's actual material, including real plastic. Do not simulate low quality with noise, blur or shake. A product-identity photo controls the product, not the photographic style; a format reference controls only its assigned roles.

Within one scene, keep the same motivated main light, compatible color temperature and exposure, and physically consistent shadows across all panels and related shots. A different camera angle changes the apparent shadow direction naturally; do not force identical screen-space shadows. Reduce distracting bright spots, mixed-color light and unexplained illumination from every direction; soft light is allowed, hard light is not mandatory. Different scenes may have different lighting. Carry these resolved choices into `shared-brief.md`, `review_style` and each image prompt before approval; do not retroactively rewrite approved projects to adopt defaults.

## User-facing creative checkpoints

For new `creative_plan_to_shot` projects, use [the creative review template](creative-review-template.md) as the single user-facing format: overall direction, batch overview, one complete six-column four-row table per storyboard, design tradeoffs/deduplication, then scope-clear batch confirmation. First determine story, product display or a mix; ask a short focused question only where the materials leave a consequential creative choice unclear. Use verified product facts and one main selling point per storyboard; discuss priorities when they conflict. Check each panel's purpose, repetition within each grid and duplication across the batch before presenting it. Do not turn this internal check into another approval round.

Keep technical syntax out of the short conversational summary, but link the complete saved prompt file for inspection before staged approval. Default delivery is the storyboard plus its matching video prompt; after the storyboard is approved as usable, prepare the video prompt automatically. “直接生成 / 跳过流程 / 无需审核 / 只生成就行” selects fast review but does not remove the video prompt unless the user explicitly says they do not want it.

The coordinator saves the full creative content in the existing plan fields and binds each displayed design using `prepare-design-review` and `approve-design`. One explicit approval of the displayed batch may support the matching per-shot records; partial approval covers only that subset. After batch approval, record the default all-shot launch without another all/pilot question; honor an explicit pilot request instead. Prepare the shared brief and actual per-shot references, then hand approved creative plans to the shot conversations, without first writing the full technical prompts. Each child copies the approved context, selling point, purpose, complete beat strings and scales into the matching production fields and prompt; see [schema.md](schema.md#six-column-creative-content-without-new-fields). It records `check-prompt-plan` only after actually checking its initial prompt against the design and whole-batch context. Local revisions remain with that child.

Single-shot work uses the same displays in the current conversation; fast mode keeps internal planning and checks without adding checkpoints. Existing `prepared_prompt_to_shot` projects retain coordinator-prepared initial prompts and their explicit all/pilot question; unmarked projects keep their original ownership and review cadence. Follow [the compatibility rules](hybrid-coordination.md) rather than rewriting an existing valid draft or approval to adopt these formats.

## Per-shot staged review

新分阶段流程使用 [生图提示词展示模板](storyboard-prompt-review-template.md)，不再另设简版格式。子对话写好完整初稿并核对后，在登记真实身份的前提下运行 `prepare-prompt-review`；展示实际参考图及用途、与当前完整文件一致的六列四格表、设计差异和真实提示词链接。用户批准当前版本后，该子对话继续生成、QA、标注、图片审核、视频提示词和交付。核心创意变化先走现有设计修订/确认，不能靠一句“技术细化”跳过。单张在当前对话使用同一结构，明确快速模式仍合并审核。

恢复任务时沿用仍有效的初稿、审核 ID 和批准，不因重新展示而重写。已有 prepared 项目继承总控已准备的初稿；无标记旧多张项目仍由总控核对并提交提示词审核。不把本节的新默认用于强制迁移历史项目。

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
【未指定其他风格时采用；否则替换为已确认风格】真实手机实拍质感，自然材质、细节和景深，不刻意添加噪点、模糊、抖动、塑料感或夸张电影效果。同场景使用【根据场景确定的主要光源与方向】，色温、曝光和阴影逻辑协调，机位变化符合实际光源关系；减少散乱亮点和杂乱混色光，不强制硬光。切换场景时允许合理的光线变化。

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

Before presenting, replace placeholder values and remove drafting notes; keep the section headings such as `【版式】` and `【产品还原】`. Fill in the actual image IDs. In new six-column designs, each panel's core description includes all approved labeled beat details verbatim, not just its product-state fragment. Distinguish the visible still state from the later video movement intent within that text; do not ask one panel to depict every moment of a move. Verify the product can physically perform the stated actions, the four scenes form a coherent sequence with specified cuts where needed, and the final panel matches the intended ending. For durations other than 4 seconds, recalculate every label and the output duration together. The skill's approved project settings take precedence over this template's example style and duration.

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

Fill the resolution placeholder from the project's `defaults.video_resolution`; use 720p only when no video resolution has been specified. Preserve existing or explicitly requested settings such as 1080p. This video-prompt default does not change the storyboard image or layout dimensions.

In staged mode, write this only after the storyboard has been approved. In explicitly requested fast mode, draft it for the combined review package and mark the storyboard and prompt as pending review until the user approves; do not describe the image as approved prematurely. `@Image1` is the corresponding storyboard, not an exact first frame; map original references to the actual upload order starting at `@Image2`. Product identity and structure come from the original product reference when the storyboard has minor detail drift. A severe storyboard error must be resolved before using it as video guidance.

### Motion in static display segments

- Judge each segment's intended person/product action, not whether its reference image is still. In mixed sequences, handle static display segments individually; do not wait until the entire video is static.
- If both subject action and camera movement are absent, plan one gentle zoom in, zoom out, leftward or rightward move that supports the selling point. State direction, modest extent, framing and endpoint. Already moving cameras need no duplicate move; subject action does not require added camera motion. Short holds, especially at the ending, are allowed.
- Keep one coherent main movement within a continuous shot, rather than reversing every time label or combining all movements. For `cuts`, retain the approved cut points and plan movement within each suitable segment; cuts between still views alone are not a substitute. Do not move across unrelated views as if they formed one continuous take.
- Keep products and people in their approved states when only the camera moves. Do not invent rotation, handling, opening, unknown backsides or altered final framing to make motion possible.
- The coordinator includes this intent in the approved creative design; in new multi-shot projects the child carries it into the existing camera plan and technical prompt. Existing prepared-prompt projects keep coordinator authorship of that initial plan. The video author refines compatible detail in video text only. An explicit or already-approved fixed camera takes precedence; a conflict needs the existing revision/confirmation flow, not silent overriding or mutation of `shot.camera`, `sequence_type`, panels or the shared brief after image approval. Fast mode follows the same content rules with its existing combined review.

Example for an approved static tabletop detail with compatible camera freedom: “书签保持静止，镜头缓慢拉近，从可见整体过渡到已确认的纹样细节，末尾短暂停稳；不旋转产品，不添加拿取动作。” Choose a different compatible move when the approved endpoint is a full-product view; this is not a compulsory zoom-in recipe.

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
[时间段4]：[最终状态、构图和符合原计划的镜头收尾方式，可短暂停稳。]
运镜：[符合已确认方案的方向、幅度、构图变化与终点；无主体动作且未安排运镜的展示段补充一种轻缓镜头运动，允许短暂停稳；明确要求或已批准的固定机位保留。]

保持：[产品身份和数量、几何结构、材质、颜色与纹样、包装版式、手部、背景光线和最终状态中与本镜头有关的项目。] 连续动作保持运动与机位衔接；剪辑序列在指定切点换视角，保持产品身份、道具及同场景光线逻辑一致，跨场景光线按已确认方案自然变化。只让上述明确指定的元素运动。
禁止：[镜头特有错误。] 避免闪烁、形变、复制部件、图案漂移、异常手指、字幕和水印。包装小字按原图视觉版式处理，不凭空增加营销文字。
声音：[已确认的音频规则]。
```

Before presenting, remove all placeholders, reconcile the four beats and final state with the matching storyboard (approved in staged mode, still pending package review in fast mode), and verify reference numbering against the actual uploaded images. Time ranges guide order and pacing; they do not promise frame-accurate alignment. If duration changes, recalculate all four ranges and keep the project duration consistent in storyboard, labels, shot manifest, and video prompt.
