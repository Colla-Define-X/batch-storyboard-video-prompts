# 执行指南

这里的命令示例中 `PROJECT` 表示实际项目目录。正常运行工作流命令时不要同时手工编辑该镜头的 JSON。只手工填写内容字段，状态、审核记录和版本由脚本管理。

## 初始化与交付范围

```bash
python scripts/workflow.py init PROJECT --name "产品展示"
```

默认1张、4秒、仅分镜图，在当前对话执行。用户需要视频提示词时增加 `--delivery storyboard_and_video_prompt`；明确需要多张时增加 `--shots N`。已有项目不能重新init；读取现有清单继续。

将全局设置、原始参考图预览与完整分镜提示词合并展示，可一次完成单张项目的确认。使用已授权快速模式时，直接按用户设置与缺省值准备文件。

```bash
python scripts/workflow.py add-source PROJECT ORIGINAL_PHOTO --id image-01
```

填写 `shared-brief.md`，保存 `shots/shot-01/storyboard-prompt.md`，按 [schema.md](schema.md) 填写 `shot.json` 的参考图、四段时间、标签、可见画面、运镜、不变量和 `sequence_type`。不能用空文件或一句无具体内容的标题代替完整提示词。模板质量需由agent检查，脚本不会理解产品语义。

## 分阶段执行

用户确认前只进入待审核状态：

```bash
python scripts/workflow.py status PROJECT shot-01 storyboard_prompt_pending
```

用户明确批准当前完整提示词后：

```bash
python scripts/workflow.py approve PROJECT shot-01 storyboard_prompt --note "用户批准当前提示词"
python scripts/workflow.py preflight PROJECT shot-01
```

`preflight` 验证提示词、参考文件哈希、四格数据与批准版本，并分配 `vNN`。它为一次工具调用登记授权；同一授权重复调用会失败。此后读取提示词，记录实际工具输入为 `generation-prompt-vNN.md`，立即调用生图，并将结果保存为 `storyboard-vNN.png`。不要先生成再补preflight。

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

检查裁切未丢失主体、四格完整、标签无错误且不遮挡重点。记录 `qa.result=pass` 或 `pass_with_notes` 与具体偏差。严重失败记录 `generation_failed`；不自动再次生图。

```bash
python scripts/workflow.py status PROJECT shot-01 storyboard_review_pending
```

展示实际review图片，等待用户批准，再执行：

```bash
python scripts/workflow.py approve PROJECT shot-01 storyboard --note "用户批准当前分镜"
```

命令复制为 `storyboard-final.png`，写入冻结哈希清单 `storyboard-final.json`，保留所有编号版本。仅图片项目至此 `complete`。

组合项目继续：依据获批图片写 `video-prompt.md`，执行 `status ... video_prompt_review_pending`，展示后等待批准，再 `approve ... video_prompt --note ...`。缺文件或图片哈希变化时不能完成。

## 快速模式

保存相同的完整提示词与镜头内容，记录用户明确的请求：

```bash
python scripts/workflow.py set-mode PROJECT shot-01 fast --reason "用户明确要求快速模式"
python scripts/workflow.py status PROJECT shot-01 running
python scripts/workflow.py preflight PROJECT shot-01
```

生成和QA与上文一致。只要图片就交图片；组合交付先补好视频提示词草稿，再进入 `review_pending`。整体获批后用 `approve ... review_package` 冻结与完成。

在 `todo` 或 `storyboard_prompt_pending` 可记录快速模式请求；已进入生成流程后，要修改前序内容先 `revise ... storyboard_prompt --reason ...`，再切换模式，不伪造已完成的审核。

## 重试、修订与过期批准

- 图片审核中或失败后，用户明确要求再生成：`retry PROJECT shot-01 storyboard_generating --reason ...`（快速模式目标为 `running`）。随后重新preflight，分配新版本。
- 视频提示词失败只能返回 `video_prompt_pending`；图片失败不能跳到视频。
- 改产品、参考图、文字提示词、场景、时间或画面描述：`revise PROJECT shot-01 storyboard_prompt --reason ...`，修改文件，再按对应模式继续。
- 已批准图片要求重做：`revise PROJECT shot-01 storyboard --reason ...`。保留提示词批准，只失效图片及视频批准；若提示词也变化必须改用上一条。
- 只改视频提示词：组合项目用 `revise PROJECT shot-01 video_prompt --reason ...`。分阶段返回视频提示词待生成；快速模式失效旧整体批准并返回审核包待确认。两者均保留当前图片，修改视频提示词后重新审核，不要求重新生图。

审核记录绑定输入、图片版本和哈希。修改后命令会报告stale，必须修订/重新批准，不通过直接改JSON绕过。普通status不允许退回重生成。

## 并发、恢复与旧项目

单张禁止 `set-concurrency` 和 `register-task`。多张授权并发后按hybrid-coordination执行；每个镜头有一个内容维护者，公共设置由当前主对话管理。状态与批准命令可以由授权的镜头对话调用，它们会在项目锁内更新镜头和项目摘要。

命令用操作系统锁串行执行完整读改写，并用 `.workflow-transaction.json` 保存受影响控制文件的旧内容；异常时恢复整组文件。进程意外退出后，下一个工作流命令先恢复未完成事务。锁等待有上限，busy错误需等前一命令退出后重试，不能删锁文件抢占。文件修改绕过脚本时不受锁保护。

```bash
python scripts/workflow.py migrate PROJECT
python scripts/workflow.py validate PROJECT
```

仅显式迁移schema-v3。成功时保留项目与每个镜头的 `.bak`，有效旧时间划分保持不变。旧批准无法可靠绑定当前文件，迁移保留历史并将已推进镜头放回提示词待确认；不制造批准。失败恢复全部受影响文件，移除本次未提交的备份，使修正错误后可再次迁移。

旧schema-v4没有绑定的批准不能直接推进；用revise恢复到相应审核步骤。不要为继续旧任务而关闭检查。

`validate` 是文件、哈希与状态检查，不替代人工语义判断和视觉QA，也不能在操作系统层拦截绕过脚本的生图工具调用。
