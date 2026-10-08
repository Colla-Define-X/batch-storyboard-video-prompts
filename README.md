# Batch Storyboard Video Prompts

根据产品参考图、成组图片或镜头想法设计可审核的 **9:16 四宫格视频分镜图**，并为每个镜头生成与已确认分镜一致的**视频生成提示词**。

这个仓库本身就是一个可安装的 Codex skill：仓库根目录包含 `SKILL.md`，克隆后无需构建即可被 Codex 读取。

## 能做什么

- 在项目层统一确认画幅、布局、镜头时长、视觉连续性、声音与交付范围。
- 对新建多张分阶段项目，主对话先按使用情境与可靠卖点规划整批内容，再完成每张初版完整提示词；镜头对话接手各自的审核与制作。
- 每镜头默认交付分镜图与匹配的视频提示词；分镜确认可用后自动进入视频提示词阶段。
- 支持多个镜头并行推进，且不会让一个镜头的审核阻塞其他镜头。
- 未指定数量时默认生成1张；单张在当前对话完成。多张分阶段制作使用独立镜头对话并行推进；明确要求快速模式或直接生成时在当前对话集中产出。
- 稳定保存参考图、SHA-256 哈希、镜头状态和分镜版本。
- 将四张无标签画面确定性排版为 9:16、2×2 的带时间标签分镜图。
- 提供显式请求才启用的快速模式，一次提交完整审核包。

当用户提出“生成分镜图”“设计分镜图”“制作视频分镜”“我想做视频分镜图”等制作请求时，可触发本 skill。不要求用户必须提到“批量”或“四宫格”。仅询问分镜概念、分析或评价已有分镜时，不进入制作流程。

## 安装

### 方法一：让 Codex 直接从 GitHub 安装

在 Codex 中调用 `$skill-installer`，明确指定仓库根目录和安装名：

```text
请用 $skill-installer 安装 https://github.com/Colla-Define-X/batch-storyboard-video-prompts.git 根目录的 skill；安装参数为 --repo Colla-Define-X/batch-storyboard-video-prompts --path . --name batch-storyboard-video-prompts。
```

安装器负责取得 skill 文件，不会安装本仓库的 Python 依赖。安装成功后，进入安装器返回的目录运行 `python -m pip install -r requirements.txt`（Windows 可用 `py -m pip install -r requirements.txt`）。

### 方法二：用户级安装

安装后，该 skill 可用于你的所有 Codex 项目。

macOS / Linux：

```bash
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/Colla-Define-X/batch-storyboard-video-prompts.git \
  "$HOME/.agents/skills/batch-storyboard-video-prompts"
python -m pip install -r "$HOME/.agents/skills/batch-storyboard-video-prompts/requirements.txt"
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.agents\skills" | Out-Null
git clone https://github.com/Colla-Define-X/batch-storyboard-video-prompts.git `
  "$env:USERPROFILE\.agents\skills\batch-storyboard-video-prompts"
py -m pip install -r "$env:USERPROFILE\.agents\skills\batch-storyboard-video-prompts\requirements.txt"
```

### 方法三：仅在某个仓库中使用

在目标仓库根目录执行：

```bash
mkdir -p .agents/skills
git clone https://github.com/Colla-Define-X/batch-storyboard-video-prompts.git \
  .agents/skills/batch-storyboard-video-prompts
python -m pip install -r .agents/skills/batch-storyboard-video-prompts/requirements.txt
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force -Path .agents\skills | Out-Null
git clone https://github.com/Colla-Define-X/batch-storyboard-video-prompts.git `
  .agents\skills\batch-storyboard-video-prompts
py -m pip install -r .agents\skills\batch-storyboard-video-prompts\requirements.txt
```

Codex 会扫描仓库路径中的 `.agents/skills`。如果安装后没有立即出现，请重启 Codex。
上述克隆命令用于首次安装；如果目标目录已存在，先检查其中的来源和本地修改，不要直接覆盖。

## 使用

在 Codex 中直接提及 skill：

```text
$batch-storyboard-video-prompts

请把这些产品参考图拆成 4 个镜头。每个镜头生成一个 9:16 四宫格分镜，
分段确认核心创意，逐镜头审核分镜图和视频提示词。
```

也可以明确要求快速模式：

```text
$batch-storyboard-video-prompts

用快速模式处理这些参考图，按镜头给我一次性审核包。
```

默认模式适合客户交付和高保真产品内容。单张分镜在当前对话确认与制作。新建多张分阶段项目由主对话先规划整批、逐张确认四句简短画面，并完成**所有镜头**的初版完整提示词和整批核对；准备完毕才问用户“全部开始，还是先做 1–2 张”，之后创建独立镜头对话。每个镜头对话收到现成提示词，在自己对话里展示简明方案和完整文件链接，得到对这一张当前版本的确认后继续图片、QA、视频提示词和交付，不必常规返回主对话复核或汇总。脚本将内容规划与提示词绑定，避免把项目总体方向确认误记为单张提示词批准。生成后仍由助手做视觉 QA，用户最终判断图片是否可用。

创意确认绑定具体设计版本：修改场景、卖点、四格或景别后，旧确认不能继续使用。脚本核对技术提示词对应的核心描述和景别；新建多张项目由主对话在初次交接前记录每张语义与跨分镜核对，镜头对话负责本张后续局部修订。这些是内部记录，不额外增加用户确认轮次。修改某张未完成的草稿不阻塞其他已批准分镜，共同风格或全片关系的改动则可能影响多张，需要另行协调。

“生成”“批量生成”“生成分镜图”和“设计分镜图”都只表示开始制作，仍然使用默认分阶段模式。只有用户明确提出“直接生成”“不用确认”“跳过审核”“一次出完”“合并审核”或“快速模式”时，才切换为快速模式并记录该要求。多张图的快速模式在当前对话集中产出，不创建逐镜头对话；默认仍交付匹配的视频提示词，除非用户明确只要图片。

## 工作流概览

```text
核实产品事实，判断故事演绎或产品展示
        ↓
主对话规划整批场景、卖点、四格画面和景别，逐张确认
        ↓
新多张项目：主对话先完成全部初版提示词和核对，再选择并发方式、创建镜头对话
        ↓
各镜头对话确认本张提示词 → 生成后 QA → 用户审核图片 → 视频提示词
        ↓
各镜头对话完成视频提示词审核并交付自己的结果（仅要图则在图片审核后结束）
```

## 多张分镜图的分阶段并行

以下协调流程适用于两张及以上、未要求快速模式的分镜。未指定数量或只要一张时，在当前对话完成，不询问并发方式：

- 主对话维护共享 brief、整批规划、公共设置和参考图；新项目先确认每张展示情境、主卖点与四格画面，再写完所有初版提示词和对应镜头内容、核对整批避重，最后才问“全部同时开始，还是先做 1–2 张”。
- 用户没有选择前不创建镜头任务；选择全部开始后允许所有镜头并发，选择试做后只启动指定的 1 或 2 个。
- 独立镜头对话默认仍留在主对话所在的 Codex 项目中；主对话无项目时，子对话也无项目。助手在创建前确认归属、创建后核对结果，正常不增加用户问答；只有归属无法核实或结果不符时才暂停说明，不擅自另选项目或重复创建。文件保存目录和侧边栏分组不等于对话归属；已有对话不会因此自动搬迁。明确指定其他归属时按你的要求核实后创建，详见 [创建规则](references/hybrid-coordination.md#project-membership-when-creating-conversations)。
- 试做是本轮的镜头范围，不是滚动队列；完成或释放后不会自动放行下一张，同一轮中同一张返工不增加新的试做镜头，但仍须取得活动生图名额。
- 一批中只有部分镜头明确要求快速模式时，仅普通分阶段镜头创建任务；快速镜头留在当前对话。切换已有活动任务前先释放槽位。
- 新项目的镜头对话接收已写好的完整初稿，等真实任务身份登记后，在该对话首次展示和确认提示词；此后继续本张图片、标签、视觉 QA、图片审核、视频提示词和交付。主对话不做常规回收审核或最终汇总。局部创意修改可在本镜头对话完成确认；涉及全局或其他镜头才另行协调。
- 分镜获批后释放的是并发生图名额，不关闭镜头对话；同一对话继续视频提示词，不重新登记或生图。以后确实要重做图片，仍须符合当时的启动选择和任务登记，旧一轮试做的资格不能跨轮沿用。
- 图片生成失败时不自动重试；小问题也先交用户审核。

明确要求快速模式或直接生成多张时，在当前对话依次准备每张图的内部提示词、执行生成前检查与质量检查，并集中展示结果；不创建逐镜头对话，也不采用单对话逐张分阶段审核。

已有项目若没有新交接标记，仍按原来的“镜头任务写初稿、主对话核对并确认提示词、主对话负责视频提示词”继续；即使尚未选择并发，也不自动改成新流程。单张和快速模式也不改变分工。

这种拆分方式遵循 [OpenAI 的长任务建议](https://learn.chatgpt.com/docs/long-running-work)：相关工作尽量留在同一对话共享上下文，只有能够独立执行的任务才拆分到不同对话并行。

关键约束：

- 新项目须在选择并发或生成前填写已确认的 `content-plan.json`；单张也要明确表达目的。四格默认至少三种有效景别，有叙事理由时可例外。
- 每格提供新的动作、产品状态或信息；避免首尾及跨分镜重复。卖点过多时先与用户讨论优先级，不强加故事，也不编造产品能力。
- 单张 9:16 图片恰好包含四个有顺序的画面；根据动作选择连续过程或明确切镜。
- 每个镜头不得短于 4 秒，普通产品镜头默认 4 秒，多数镜头保持在 4–10 秒。
- 通常先生成无标签画面，再通过脚本添加时间与动作标签；用户明确要求直接生成标签时检查后不重复添加。
- 保留所有 `storyboard-vNN.png`，不覆盖历史版本。
- 未经用户单独授权，不提交可能收费的视频生成任务。

## 辅助脚本

默认初始化一张、4秒、分镜图加视频提示词的项目：

```bash
python scripts/workflow.py init ./demo-project --name "产品展示"
```

用户明确只要图片时加 `--delivery storyboard_only`；多张加 `--shots N`。完整技术提示词在后台保存；记录创意设计批准或快速模式授权后，必须执行 `preflight` 才能调用生图。

命令、版本命名、拆格、冻结、修订、重试与旧项目迁移见 [执行指南](references/execution.md)。不要使用旧版“只有状态、没有文件”的操作示例。

本地旧测试项目如果已启用内容规划、但仅存有确认文字，需要重新绑定当前创意设计并核对提示词；不会自动把旧文字转换成批准。无新交接标记的旧项目仍走原有分工，显式 v3 迁移也不会为它加标记。

状态和可变内容保存共用跨进程锁。`save-content` 校验所编辑的文件版本，拒绝用旧草稿覆盖新内容；失败仅回滚本次实际写过的文件。发现外部改动冲突时保留当前文件和恢复日志，停止自动恢复。批准绑定实际产物哈希，内容变化会使旧批准失效。重做分配新版本，排版拒绝覆盖已有输出。

用户要求两张设计互换时，使用成组创意修订退役对应旧分工，再逐张确认新设计；历史保留，其他镜头不必重审。提示词已提交待确认时，任务恢复不会再要求继续编写该提示词。

创意、提示词和产物每次正式提交审核使用独立 ID；撤回后重新提交，即使内容相同也不能复用撤回前的回复。有效且未撤回的确认不重复询问。图片、视频提示词和快速审核包还绑定提交时的版本及 QA。待图片/快速包审核时可以只补充 QA 说明，保留原图，说明实际变化后重新展示确认；严重问题则记录失败并停止，等待用户决定，不自动重做。快速模式只修改视频文案时保留原图。多张分阶段每次新生图前会再次检查活动任务与**当前轮**试做范围；图片获批、任务释放后不影响同一镜头对话继续视频提示词。

在途生成未返回完整结果前不能通过修订重开；本次图片已返回且 QA 通过时，即使要求已变，也能进入提示词/设计修订，不把成功返回误判为仍在生成。旧图保留，但不能因此作为满足新要求的获批成品。真实失败可如实记录，后续生成仍要求有效的当前授权，脚本不会取消外部生图调用。交付范围目前只支持前期调整：全项目没有提示词/产物批准及生成历史时，尚未批准的提示词审核可以先撤回，再调整范围。已经有批准或生成历史的项目不支持完整中途范围切换，不会为此重写旧批准或自动重做图片。

## 仓库结构

```text
.
├── SKILL.md                  # 主工作流与强制约束
├── agents/openai.yaml        # Codex 展示与调用元数据
├── references/               # 模式、数据结构与提示词模板
├── scripts/                  # 项目协调、排版和预览工具
├── tests/                    # 自动化测试
├── SPEC.md                   # 当前用户可感知行为与验收基线
├── VERSION                   # 当前发布版本
└── CHANGELOG.md              # 版本变更记录
```

## 版本管理

本项目遵循 [Semantic Versioning](https://semver.org/)：

- `MAJOR`：不兼容的工作流、数据结构或命令行变更。
- `MINOR`：向后兼容的新能力。
- `PATCH`：向后兼容的修复或文档改进。

每次发布时：

1. 更新 `VERSION`。
2. 把 `CHANGELOG.md` 的 `Unreleased` 内容移入对应版本和日期。
3. 运行 `python scripts/check_release.py` 与 `python -m unittest discover -s tests -v`。
4. 提交本次发布的变更，包括新增的 `SPEC.md` 等必需文件。
5. 在准备发布的分支运行 `python scripts/check_release.py --release`。它检查当前提交 `HEAD` 中的必需文件是否齐全，并拒绝这些文件尚有暂存或未暂存的修改，避免本地通过检查却漏发文件。此步骤要求 skill 本身是 Git 仓库根目录，不能借用上层目录的仓库。
6. 检查通过后，按 `VERSION` 中的版本号创建带注释标签：`git tag -a vX.Y.Z -m "Release vX.Y.Z"`（把两处 `X.Y.Z` 替换为 `VERSION` 的实际内容），再按发布目标推送分支和标签。检查本身不会提交、打标签、合并或推送。

查看当前版本：

```bash
python scripts/check_release.py
```

不带 `--release` 的本地检查不调用 Git，也适用于安装器下载的无 `.git` 副本；`--release` 只用于维护者提交后、打标签前检查必需文件的提交完整性。

## 更新已安装版本

通过方法二或方法三 `git clone` 安装的，进入该 skill 的安装目录，先查看并保留需要的本地修改，再执行：

```bash
git status --short
git pull --ff-only
python -m pip install -r requirements.txt
```

通过方法一 `$skill-installer` 安装的，默认下载副本不保证带有 Git 元数据，不能把 `git pull` 当作更新步骤。安装器也不会覆盖已存在的目标目录。需要更新时，先检查旧目录中的个人修改；经你确认，将旧目录移到 Codex 不扫描的备份位置，再重新运行方法一安装到原名称，核对差异并验证新版。不要直接覆盖或删除旧目录。切换后在新目录重新安装 `requirements.txt` 中的依赖。若希望以后直接用 `git pull --ff-only` 更新，首次安装请选择方法二或方法三。

如更新未在 Codex 中显示，请重启 Codex。

## 运行测试

```bash
python -m pip install -r requirements-dev.txt
python scripts/check_release.py
python -m unittest discover -s tests -v
```

## 兼容性

- 完整的“每镜头独立可见任务”工作流以具备任务创建能力的 Codex Desktop 为正式支持环境。
- Codex CLI 和 IDE extension 可以使用辅助脚本及当前会话内的分阶段流程，但不保证提供独立可见任务。
- Python 3.10+。
- Git 安装和项目协调脚本支持 Windows、macOS、Linux。
- 带中文标签的联系表目前以 Windows 中文字体环境为正式支持范围；`storyboard_layout.py` 在其他系统可通过 `--font` 指定字体，`reference_preview.py` 暂不提供自定义字体参数。

## 文档

- [当前行为与验收规格](SPEC.md)
- [主工作流](SKILL.md)
- [严格分阶段模式](references/strict-mode.md)
- [总控与轻量镜头任务](references/hybrid-coordination.md)
- [项目数据结构](references/schema.md)
- [提示词模板](references/prompt-templates.md)
- [变更日志](CHANGELOG.md)

本 README 的安装位置和发现规则参考了 [OpenAI 官方 skills 文档](https://learn.chatgpt.com/docs/build-skills)。
