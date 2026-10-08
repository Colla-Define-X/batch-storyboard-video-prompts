# 执行指南

这里的命令示例中 `PROJECT` 表示实际项目目录。内容在各自的草稿文件中编写，再用下述带锁命令保存；不要直接覆盖项目的 JSON、共享 brief 或提示词。状态、审核记录和版本只能由工作流命令管理。

## 安全保存内容

先取得目标文件的版本，再读取其内容并编写自己的草稿：

```bash
python scripts/workflow.py content-revision PROJECT shots/shot-01/shot.json
python scripts/workflow.py save-content PROJECT shots/shot-01/shot.json --from-file OWNER_DRAFT.json --expected-hash HASH
```

`OWNER_DRAFT.json` 对 `shot.json` 是只含要更新内容字段的补丁，例如 `{"camera":"已确认的运镜"}`；不得包含状态、批准、任务和版本字段。`project.json` 只允许补丁修改 `name`、`defaults`、`delivery_scope`，由总控维护。`content-plan.json` 保存完整规划对象；`shared-brief.md`、`storyboard-prompt.md` 和 `video-prompt.md` 保存完整文本。每次保存前重新取得该文件版本；新文件使用命令返回的 `missing`。草稿放在不与其他任务共用的路径中，不直接写目标文件。

发生版本冲突时，保留草稿、重新读取目标并合并内容，再保存；不能只换一个新哈希重试旧草稿。已批准的提示词要先 `revise`；生成中只允许更新 QA 和面板图片路径，不能修改核心画面。生图原图、编号版成图和实际工具输入属于独立版本产物，仍按原规则保存，不覆盖旧版本。

`delivery_scope` 是全项目范围，不是单张设置。前期所有镜头都在编写阶段（`todo` 或 `storyboard_prompt_pending`）、没有待确认的提示词审核、没有提示词/产物批准及生成历史时可以调整；待确认的创意设计审核本身不锁定范围。若只是提交了尚未批准的提示词审核，先按用户要求用 `revise ... storyboard_prompt --reason ...` 撤回该审核，再调整范围。任一镜头不满足这些条件时，拒绝直接修改整个项目范围；撤回已有批准不等于删除批准历史。同值保存和修改项目名称不受此限制。当前版本不支持保留旧产物的中途范围转换；遇到该需求先说明限制并询问下一步，不强制用户继续原交付，也不擅自新建项目、重做图片或修改旧批准。

## 初始化与交付范围

```bash
python scripts/workflow.py init PROJECT --name "产品展示"
```

默认1张、4秒、分镜图加匹配的视频提示词；单张在当前对话执行。只有用户明确说“只要分镜图”或“不要视频提示词”时才增加 `--delivery storyboard_only`；明确需要多张时增加 `--shots N`。新项目带 `workflow.handoff_model: prepared_prompt_to_shot`，仅多张分阶段镜头采用下面的新交接：总控准备初版完整提示词，子对话接手审核和后续制作。单张、快速镜头仍在当前对话。没有此标记的已有项目继续原来的总控审核/视频路线，即使尚未选择并发也不自动转换。已有项目不能重新 init；读取现有清单继续。

新项目先填写 `content-plan.json`：判断故事、产品展示或混合形式；核实产品事实；内部规划整批；默认逐张向用户展示场景、主卖点和四句简短画面并确认。卖点过多时先讨论优先级，信息不足时不编造功能或故事。新多张分阶段项目在创意确认后，由总控完成**每张**初版 `storyboard-prompt.md`、对应 `shot.json` 内容和 `check-prompt-plan`，全部准备好才询问“全部开始还是先做 1–2 张”并创建子对话。明确快速模式仍要内部规划；普通“生成”不跳过确认。

单张由当前对话编写并核对技术提示词。新多张分阶段项目由总控完成各初版提示词及整批核对，子对话接到完整文件后不要重新起稿；在**该子对话**提交当前提示词审核，展示简明四格方案并用本地文件链接提供完整提示词。用户在看到两者后的明确确认才批准该镜头当前版本；此后该子对话继续图片、QA、视频提示词和交付，不按常规回主对话审核或汇总。已有无标记项目保留“子任务写初稿、总控核对并提交提示词审核、总控完成视频”的原流程。此前的创意方向确认、并发选择和沉默均不算提示词批准。

## 创意版本确认与提示词交接

规划文件先填写设计内容，不手填批准记录。逐张展示之前运行：

```bash
python scripts/workflow.py prepare-design-review PROJECT shot-01
```

把简短场景、主卖点、四格内容展示给用户；审核标识只供内部记录。得到对该版设计的回复后：

```bash
python scripts/workflow.py approve-design PROJECT shot-01 --review-id DESIGN_ID --confirmation "用户对本张设计的实际回复"
```

这两条命令落实原有的创意确认，不增加一轮用户问答。设计内容变化后旧标识失效；保存旧确认文字不能放行。记录保存在对应 `shot.json` 的 `design_review` 和 `design_approvals`，`content-plan.json` 的确认文字仅作可读摘要。明确快速模式时先记录 `set-mode ... fast --reason ...`，设置该张 `approval_source: explicit_fast_request`，再内部准备并以实际跳过请求记录设计授权，不向用户索取额外设计批准。

创意和提示词每次正式提交都有独立审核 ID，内容相同也不复用上一轮 ID。用户撤回创意批准时用 `revise-designs` 退役对应设计，撤回提示词审核/批准时用 `revise ... storyboard_prompt`；重新提交后展示当前版本，取得本轮回复。没有修改、撤回或重新提交时，不重建有效审核、不要求重复确认；旧有效批准不会因这项更新被批量改写。

负责编写的对话按已确认设计逐字填写 `review_context`、`review_selling_point`、`review_purpose`，并按左上、右上、左下、右下顺序填写四格：`description` 对应 `panel_beats`，`shot_scale` 对应 `shot_scales`，`plan_panel_id` 使用本镜头 ID 加 `:panel-1` 至 `:panel-4`（例如第二张为 `shot-02:panel-1`）。技术补充另写，不替换核心描述。完整提示词包含场景、目的、卖点、风格、各格核心描述、时间、标签和对应中文景别（wide=全景、medium=中景、close=近景、macro=微距）。

新多张分阶段项目由总控在交接前实际核对每张初版提示词与规划、各格景别和整批动作是否一致，再逐张记录；单张/快速模式由当前对话负责，已有无标记项目仍由总控在收到子任务初稿后负责：

```bash
python scripts/workflow.py check-prompt-plan PROJECT shot-01 --note "本次核对的具体结论，包括与其他分镜的区别"
```

新交接后若用户只要求修改本镜头，子对话自己重新核对并记录本张的新 `check-prompt-plan`，无须再回总控做一次常规检查；真正影响全局或其他镜头的修改应另行协调。脚本检查结构化对应关系及提示词包含的核心内容，并绑定核对版本；不判断近义表达是否重复、不证明图片质量。提示词或其输入变化后核对记录过期，必须重新核对。不要把这项内部工作变成用户的新确认问题。

```bash
python scripts/workflow.py add-source PROJECT ORIGINAL_PHOTO --id image-01
```

填写 `shared-brief.md` 和 `content-plan.json`；新项目的计划结构见 [schema.md](schema.md)。新多张分阶段项目由总控在并发选择前保存每张 `shots/<shot-id>/storyboard-prompt.md`，按该设计填写各 `shot.json` 的参考图、四段时间、标签、可见画面、运镜、不变量、`sequence_type`、`review_style` 和 `review_selling_point`；单张/快速仍由当前对话填写，无标记旧项目维持原分工。完整提示词中须逐字包含这两项和四格的时间、标签、核心画面描述；可在其后补充摄影和生成约束。脚本检查内容规划、文件和哈希；初版编写者仍须检查近义动作与整体叙事冲突。生成后的视觉 QA 照旧执行。

## 分阶段执行

用户确认提示词前只进入待审核状态。新多张分阶段项目由总控在初版文件与本张 `check-prompt-plan` 就绪后、选择并发前逐张进入此状态；初次 `set-concurrency` 和首次任务登记还会检查完整当前提示词与核对记录，但不会代替用户批准：

```bash
python scripts/workflow.py status PROJECT shot-01 storyboard_prompt_pending
```

保存方案后，先准备本镜头的审核记录。新多张分阶段项目由已登记真实 `threadId`（及可用 `hostId`）的子对话执行；若子对话先启动，必须等总控登记并告知本任务自己的身份，不能提前提交第一次审核。单张/快速仍在当前对话；无标记旧项目按原路径由总控准备：

```bash
python scripts/workflow.py prepare-prompt-review PROJECT shot-01
```

把命令输出的简明方案放进对话，并附上 `shots/shot-01/storyboard-prompt.md` 的绝对路径 Markdown 文件链接。核对用户的回复确实发生在该方案和文件链接展示之后，且确认的是本镜头当前版本；需要修改时先修订内容，再重新运行准备命令。用户明确确认后：

```bash
python scripts/workflow.py approve PROJECT shot-01 storyboard_prompt --review-id REVIEW_ID --confirmation "用户对本镜头当前方案和提示词的确认原话"
```

仅无标记旧多张分阶段项目：总控批准成功后，通过已有协调机制向当前登记的活动镜头对话发送继续指令，恢复已空闲的任务；消息带上项目、镜头与本次提示词审核 ID。仅写入批准文件不会唤醒任务。镜头任务重新读取最新状态，核对该批准仍有效且本次生成尚未被领取，再用自己的身份执行下方 preflight；重复通知不能重开已经领取或完成的生成。新交接项目由同一子对话展示、获得用户回复并批准提示词，不需要常规返回总控或批准后再由总控通知自己。任务无法继续时按 [任务交接](hybrid-coordination.md) 处理。这是助手内部交接，不要求用户再次说“继续”。

生成前，单张在当前对话执行：

```bash
python scripts/workflow.py preflight PROJECT shot-01
```

多张分阶段则由对应镜头任务带上自己的身份执行：

```bash
python scripts/workflow.py preflight PROJECT shot-01 --thread-id OWN_THREAD_ID --host-id OWN_HOST_ID
```

身份来自总控在任务创建、登记后传入的真实任务 ID 与 host，不从 `project.json` 抄当前负责人。注册时没有 host 的，调用时也省略 `--host-id`；否则必须完全匹配。缺少身份时由总控补齐交接，不要求用户提供编号；创建结果只有 `clientThreadId` 时先等待真实 ID，不能用占位值。详见 [任务交接](hybrid-coordination.md)。

`approve` 检查审核记录标识、提示词及镜头方案哈希与当前文件一致，并保存确认依据。它无法读取聊天记录或判断用户话语的真实指向；不得用此前对项目方向的笼统确认填充 `--confirmation`。

已有有效提示词审核记录时，`task-brief` 只要求展示后等待，不再要求继续编写或重新准备审核 ID；记录过期则要求核对变化并重新提交。新交接的子对话若在本镜头修订后发现设计资料尚未完整或未确认，先在本对话补齐并确认本镜头设计，再做提示词核对和审核，不需常规回总控重审。不要因为任务恢复或重新交接而擅自改写正在等待用户确认的版本。

`preflight` 验证提示词、参考文件哈希、四格数据与批准版本，并分配 `vNN`。它为一次工具调用登记授权；同一授权重复调用会失败。此后读取提示词，记录实际工具输入为 `generation-prompt-vNN.md`，立即调用生图，并将结果保存为 `storyboard-vNN.png`。不要先生成再补preflight。

多张分阶段镜头还必须有已记录的**当前轮**启动选择和活动任务，调用者的任务 ID 与 host 必须匹配当前登记；试做范围外、身份缺失或不符都不能取得生成许可，也不会分配版本。检查失败后交总控核对，不改用别人的 ID 重试。单张和明确快速镜头不需要任务。这里只检查每次**新生图**的启动许可，不把任务是否仍活动当成已有图片或后续视频提示词有效的条件；获批后原子对话可在无活动槽位时继续视频。日后按用户要求重做图片仍须重新满足当前并发范围与活动身份，旧轮试做镜头不能借曾经入选绕过新轮范围。已经发出的生图仍须等真实结果或失败；任务释放与接手不会取消调用或重置已使用的许可。

## 四宫格到带标签成图

正常做法是生图时保留产品/构图要求、暂不渲染文字，之后准确排字。如果用户明确要求直接生成标签，则检查生成标签后保存review版，不再叠字。

对于无标签四宫格，先目视确认确为等分2×2并测量中央分隔线像素宽度；以下参数是示例，不可盲用8像素：

```bash
python scripts/storyboard_layout.py split PROJECT/shots/shot-01/storyboard-v01.png PROJECT/shots/shot-01/panels --version 1 --divider 8
```

拆分得到 `panel-v01-01.png` 至 `panel-v01-04.png`。将其相对路径写入对应panel的 `image` 字段（例如 `panels/panel-v01-01.png`）；这属于产物路径，不改变已批准的画面描述。排版：

```bash
python scripts/storyboard_layout.py PROJECT/shots/shot-01/shot.json PROJECT/shots/shot-01/storyboard-review-v01.png
```

脚本要求9:16画布、四个面板与标签，自动统一缩小过长标签的字号，过长到无法阅读则报错；默认拒绝覆盖任何已有输出。如果原图分格不均匀，不使用等分裁切冒充正确结果；先处理布局问题并遵循用户的重试决定。拆分和排版属于布局处理，不用它们改变主体图像内容。

检查裁切未丢失主体、四格完整、标签无错误且不遮挡重点。记录 `qa.result=pass` 或 `pass_with_notes` 与具体偏差。严重失败时，分阶段镜头进入 `generation_failed`，快速模式镜头进入 `failed`；不自动再次生图。

```bash
python scripts/workflow.py status PROJECT shot-01 storyboard_review_pending
```

展示实际review图片，等待用户批准，再执行：

```bash
python scripts/workflow.py approve PROJECT shot-01 storyboard --review-id ARTIFACT_ID --confirmation "用户对当前图片的确认原话"
```

命令复制为 `storyboard-final.png`，写入冻结哈希清单 `storyboard-final.json`，保留所有编号版本。仅图片项目至此 `complete`。

组合项目继续：依据获批图片写 `video-prompt.md`，执行 `status ... video_prompt_review_pending`，展示后等待批准，再 `approve ... video_prompt --review-id ARTIFACT_ID --confirmation "本版确认原话"`。新多张分阶段项目由**同一镜头子对话**完成这些步骤和交付；图片获批会释放生图活动槽位，但保留该子对话的 thread/host，视频阶段无需重新登记或 preflight。单张/快速仍在当前对话；无标记旧多张分阶段项目继续由总控完成视频提示词。缺文件或图片哈希变化时不能完成。

### 产物审核版本

进入 `storyboard_review_pending`、`video_prompt_review_pending` 或 `review_pending` 时，命令自动保存 `artifact_review` 并输出审核 ID。先记录版本，再展示对应产物和 QA；批准时带上该 ID 及随后得到的真实回复。ID 只供内部记录，不要求用户理解或输入。图片、视频文本、QA 或绑定输入变化后不能沿用旧回复。

等待确认期间，按用户要求修改视频提示词后，`save-content` 会使旧产物审核失效；修改完成后运行：

```bash
python scripts/workflow.py prepare-artifact-review PROJECT shot-01
```

随后重新展示修改后的产物，再等待并批准新 ID。不要为了批准旧回复而重新准备当前文件的审核。未修改且审核有效时继续等待，不重复准备。图片重做仍走 `retry` / `revise` 与新编号，不覆盖旧图。重新提交不会增加审核轮次，只落实原有的修改后复审。

在 `storyboard_review_pending` 或快速模式 `review_pending` 中，可以用 `save-content` 保存仅含 `qa` 的补丁，例如 `{"qa":{"result":"pass_with_notes","notes":["第二格反光略亮"]}}`。这里接受 `pass`、`pass_with_notes`、`failed`；若提供 notes，须为字符串列表。轻微说明实际变化后清除旧审核，保持当前图片、版本和状态；运行 `prepare-artifact-review`，将原图与新说明一起展示后确认，不调用 preflight。QA 完全相同则保留原审核。不能借此修改四格、图片路径或其他字段；已批准图片的视频阶段和已完成状态不开放这个入口。

若待审核图片复查发现严重问题，保存 `qa.result: failed` 会在同一事务内把分阶段镜头转入 `generation_failed`、快速模式镜头转入 `failed`，并清除旧审核、失效下游批准；保留原图、版本和已使用的生成许可，项目摘要同步更新。展示问题并停止，不重新提交为可批准图片，也不自动重做。用户明确要求再生成后，才走原有 `retry --reason` 和 preflight；仅图片失败不能跳到视频阶段。状态由保存命令管理，补丁仍禁止包含 status 或批准字段。

## 快速模式

保存相同的完整提示词与镜头内容，记录用户明确的请求：

```bash
python scripts/workflow.py set-mode PROJECT shot-01 fast --reason "用户明确要求快速模式"
```

随后按上面的内部设计授权、提示词交接核对步骤完成版本记录，再执行：

```bash
python scripts/workflow.py status PROJECT shot-01 running
python scripts/workflow.py preflight PROJECT shot-01
```

生成和QA与上文一致。多张快速请求由当前对话负责全部镜头，不创建逐镜头对话，也不调用 `set-concurrency` 或 `register-task`。每张图仍需单独保存 `storyboard-prompt.md`、填写镜头数据、记录 `set-mode ... fast --reason`，并在每次生图前对对应镜头执行 `preflight`；逐张检查成图与排版，最后在当前对话集中展示审核包。快速模式只改变审核节奏，不改变默认组合交付：先为组合交付的每张图补好视频提示词草稿，再进入各自的 `review_pending`，记录产物审核 ID 后展示。只有用户另行明确拒绝视频提示词时才只交图片。整体获批后逐镜头执行 `approve ... review_package --review-id ARTIFACT_ID --confirmation "用户对本版审核包的确认"` 冻结与完成。

在 `todo` 或 `storyboard_prompt_pending` 可记录快速模式请求；已进入生成流程后，要修改前序内容先 `revise ... storyboard_prompt --reason ...`，再切换模式，不伪造已完成的审核。

## 重试、修订与过期批准

- 图片审核中或失败后，用户明确要求再生成：`retry PROJECT shot-01 storyboard_generating --reason ...`（快速模式目标为 `running`）。随后重新preflight，分配新版本。
- 视频提示词失败只能返回 `video_prompt_pending`；图片失败不能跳到视频。
- 改产品、参考图、文字提示词、场景、时间或画面描述：`revise PROJECT shot-01 storyboard_prompt --reason ...`，修改文件，再按对应模式继续。
- 若改动了 `content-plan.json` 的核心设计，先重新准备并确认该张设计版本，再核对提示词；只改摄影技术细节不必重复创意确认，但仍要重新核对与审核提示词。新交接项目中，子对话可先 `revise ... storyboard_prompt --reason ...`，再仅更新本镜头的规划条目：对 `content-plan.json` 取得当前内容/哈希，整文件读取并合并本张修改，以 `save-content --expected-hash` 保存；冲突时重读合并，其他镜头条目和全局字段不得修改。本张后续设计确认、`check-prompt-plan` 和提示词审核也在子对话完成，不需要常规总控复核；涉及全局或跨镜头的变更则先另行协调。
- 已批准图片要求重做：`revise PROJECT shot-01 storyboard --reason ...`。保留提示词批准，只失效图片及视频批准；若提示词也变化必须改用上一条。
- 只改视频提示词：组合项目用 `revise PROJECT shot-01 video_prompt --reason ...`。分阶段返回视频提示词待生成；快速模式失效旧整体批准并返回审核包待确认。两者均保留当前图片，修改视频提示词后重新审核，不要求重新生图。

快速模式只改视频文本时，保存后运行 `prepare-artifact-review`，展示新版审核包再批准；不要调用 preflight。`generation_claimed` 表示授权已用，不表示工具永远在运行。生成阶段已有本次分配版本的审核图且 QA 通过，就可以按用户要求修订提示词或设计，即使共享要求、规划或参考文件随后变化/缺失，也不把已完成结果误判为仍在途。旧图保留，但不能因此批准为符合新要求的图片；直接重做、图片批准和视频阶段仍检查当前输入。尚无本次完整结果、图片无效或 QA 未通过时，先等待真实结果或记录真实失败。不能把在途调用虚报失败来重开生成，脚本不会取消外部工具。

失败可以在 brief、提示词或参考文件已经过期/缺失时记录，保留原 `generation_binding`、版本和 `failed_from`。这只记录事实，不批准新内容：失败后直接重试仍检查当前输入；输入变更时先按原规则修订并重新审核，不能靠失败状态绕过确认。

用户要求互换或一起调整多张创意设计时，先停止相关任务并释放活动槽位；在途生图先等待结果或记录失败。然后执行：

```bash
python scripts/workflow.py revise-designs PROJECT shot-01 shot-02 --reason "用户要求互换这两张的设计"
```

命令一次性退役这些镜头的旧创意批准和下游批准，保留历史，清除旧审核标识。随后用 `save-content` 更新规划，逐张准备并记录新的设计确认，再恢复相关任务。未选中的镜头不受影响。退役的旧动作不再占用新分工；新方案仍必须避免与未修订镜头或已新确认镜头重复。普通摄影细节修改继续使用 `revise ... storyboard_prompt`，不用退役创意设计。

审核记录绑定输入、图片版本和哈希。修改后命令会报告stale，必须修订/重新批准，不通过直接改JSON绕过。普通status不允许退回重生成。

## 并发、恢复与旧项目

单张禁止 `set-concurrency` 和 `register-task`。多张分阶段制作按 [hybrid-coordination.md](hybrid-coordination.md) 创建独立镜头对话并行推进；暂不使用单对话管理多张图各自的分阶段审核。多张快速请求使用上文的当前对话集中路径。新项目的 `workflow.handoff_model: prepared_prompt_to_shot` 仅在多张分阶段镜头上启用：总控初版准备完成后首次 `set-concurrency`，此时设置 `video_prompt_owner: shot_task`；无标记旧项目的并发选择保留 `video_prompt_owner: coordinator` 和原提示词分工。这里的 owner 是工作流分工说明，不是新增权限系统。分阶段并发时，每个镜头有一个内容维护者，公共设置由总控对话管理。状态与批准命令通过项目锁更新镜头和项目摘要。

整批选择并发时检查完整规划；之后每张任务登记、提示词审核与生成只检查本张和公共依赖，不因另一张未完成的草稿而阻塞。共同内容形式或关系变更仍会使相关批准过期。混合模式时只为 staged 镜头登记任务，fast 镜头留在当前对话；全 fast 项目拒绝设置并发。活动任务切换 fast 前先释放槽位。

试做选择除了并发上限，还记录本轮首次登记的 1–2 个不同镜头。完成、释放、失败都不清空本轮范围；同一镜头返工可以重新登记，不能自动换下一张。用户看过试做效果并明确要求继续后，释放活动任务，再执行 `set-concurrency PROJECT all --reason "用户要求剩余镜头全部继续"`；若用户只要再试做一组，用 `pilot --count 1|2 --reason ...`。改变或重置已有选择必须记录用户实际决定，不能把“这张图可以”解释成“剩下全部继续”。旧 pilot 项目若没有范围记录，需要记录用户下一步选择，不能自动补成无限队列。

命令与 `save-content` 共用操作系统锁。新格式 `.workflow-transaction.json` 在每次实际写文件前记录该文件的旧内容与预期写入哈希；失败时只恢复本次写过的文件，不恢复无关镜头。进程意外退出后，下一个命令先恢复未完成事务。若发现目标文件被锁外修改，停止恢复并保留当前文件和日志，先人工核对合并；旧格式日志同样需明确恢复，不能贸然覆盖整批。busy需等待，不能删锁或日志抢占。锁外直接修改仍不受保存协议保护，因此所有可变内容使用 `save-content`。

```bash
python scripts/workflow.py migrate PROJECT
python scripts/workflow.py validate PROJECT
```

仅显式迁移schema-v3。成功时保留项目与每个镜头的 `.bak`，有效旧时间划分保持不变。旧批准无法可靠绑定当前文件，迁移保留历史并将已推进镜头放回提示词待确认；不制造批准，也不补写新交接标记。失败恢复全部受影响文件，移除本次未提交的备份，使修正错误后可再次迁移。

旧schema-v4没有绑定的批准不能直接推进；用revise恢复到相应审核步骤。不要为继续旧任务而关闭检查。已有任务登记沿用原字段；旧多张分阶段项目下次执行 preflight 时同样必须传入调用任务自己的 ID 与匹配的 host，不迁移或重写已经取得的许可、图片和批准。

已有有效绑定的完成记录即使没有 `artifact_review_id`，仍按旧绑定检查，不批量改写历史。旧项目若停在产物待审核但缺少 `artifact_review`，先运行 `prepare-artifact-review` 并展示当前版本，再取得新的回复；不得倒填旧审核或追认旧回复。

尚未发布的本地内容规划版若只有确认文字、没有 `design_approvals`，不会自动补造批准：在待编写阶段重新准备并确认当前设计，再完成 `check-prompt-plan`；已推进的镜头先 `revise ... storyboard_prompt`。真正没有 `content_plan_required` 的旧项目保留旧工作流。

`validate` 是文件、哈希与状态检查，不替代人工语义判断和视觉QA，也不能在操作系统层拦截绕过脚本的生图工具调用。
