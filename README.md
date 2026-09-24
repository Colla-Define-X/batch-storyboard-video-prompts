# Batch Storyboard Video Prompts

根据产品参考图、成组图片或镜头想法设计可审核的 **9:16 四宫格视频分镜图**，并为每个镜头生成与已确认分镜一致的**视频生成提示词**。

这个仓库本身就是一个可安装的 Codex skill：仓库根目录包含 `SKILL.md`，克隆后无需构建即可被 Codex 读取。

## 能做什么

- 在项目层统一确认画幅、布局、镜头时长、视觉连续性、声音与交付范围。
- 每镜头默认审核提示词与分镜图；请求视频提示词时追加对应审核阶段。
- 支持多个镜头并行推进，且不会让一个镜头的审核阻塞其他镜头。
- 未指定数量时默认生成1张；单张在当前对话完成。多张需要创建并发任务时，询问全部开始还是先做1–2个确认效果。
- 稳定保存参考图、SHA-256 哈希、镜头状态和分镜版本。
- 将四张无标签画面确定性排版为 9:16、2×2 的带时间标签分镜图。
- 提供显式请求才启用的快速模式，一次提交完整审核包。

当用户提出“生成分镜图”“设计分镜图”“制作视频分镜”“我想做视频分镜图”等制作请求时，可触发本 skill。不要求用户必须提到“批量”或“四宫格”。仅询问分镜概念、分析或评价已有分镜时，不进入制作流程。

## 安装

### 方法一：让 Codex 直接从 GitHub 安装

在 Codex 中调用 `$skill-installer`，并发送：

```text
请从 https://github.com/Colla-Define-X/batch-storyboard-video-prompts.git 安装这个 skill
```

### 方法二：用户级安装

安装后，该 skill 可用于你的所有 Codex 项目。

macOS / Linux：

```bash
git clone https://github.com/Colla-Define-X/batch-storyboard-video-prompts.git \
  "$HOME/.agents/skills/batch-storyboard-video-prompts"
python -m pip install -r "$HOME/.agents/skills/batch-storyboard-video-prompts/requirements.txt"
```

Windows PowerShell：

```powershell
git clone https://github.com/Colla-Define-X/batch-storyboard-video-prompts.git `
  "$env:USERPROFILE\.agents\skills\batch-storyboard-video-prompts"
py -m pip install -r "$env:USERPROFILE\.agents\skills\batch-storyboard-video-prompts\requirements.txt"
```

### 方法三：仅在某个仓库中使用

在目标仓库根目录执行：

```bash
git clone https://github.com/Colla-Define-X/batch-storyboard-video-prompts.git \
  .agents/skills/batch-storyboard-video-prompts
```

Codex 会扫描仓库路径中的 `.agents/skills`。如果安装后没有立即出现，请重启 Codex。

## 使用

在 Codex 中直接提及 skill：

```text
$batch-storyboard-video-prompts

请把这些产品参考图拆成 4 个镜头。每个镜头生成一个 9:16 四宫格分镜，
逐镜头审核分镜提示词、分镜图和视频提示词。
```

也可以明确要求快速模式：

```text
$batch-storyboard-video-prompts

用快速模式处理这些参考图，按镜头给我一次性审核包。
```

默认模式适合客户交付和高保真产品内容。单张分镜在当前对话确认与制作；多张在用户选择并发方式后创建授权的镜头任务，并在各阶段等待明确批准。

“生成”“批量生成”“生成分镜图”和“设计分镜图”都只表示开始制作，仍然使用默认分阶段模式。只有用户明确提出“直接生成”“不用确认”“跳过审核”“一次出完”“合并审核”或“快速模式”时，才切换为快速模式并记录该要求。

## 工作流概览

```text
全局配置与图片职责确认
        ↓
稳定化 sources/ 并记录哈希
        ↓
为每个镜头生成分镜提示词
        ↓
按交付范围审核：提示词 → 分镜图 → 按需审核视频提示词
        ↓
批准后冻结最终分镜；组合交付同时保存视频提示词
```

## 总控与可选择的并发方式

以下协调流程适用于两张及以上分镜。未指定数量或只要一张时，在当前对话完成，不询问并发方式：

- 一个总控对话维护 `shared-brief.md`、公共设置、参考图、状态看板和最终视频提示词。
- 创建并发任务前，先询问用户是“全部镜头同时开始”，还是“先做 1–2 个镜头确认效果”。
- 用户没有选择前不创建镜头任务；选择全部开始后允许所有镜头并发，选择试做后只启动指定的 1 或 2 个。
- 镜头任务只维护自己的镜头内容，读取共享文件；状态和批准通过带锁的工作流命令更新。
- 分镜获批后释放镜头任务槽位，视频提示词由总控统一生成。
- 图片生成失败时不自动重试；小问题也先交用户审核。

如果更重视节省额度，可以只使用总控对话。各镜头仍可停在不同审核阶段，但这不等于多个独立任务同时在后台运行。

这种拆分方式遵循 [OpenAI 的长任务建议](https://learn.chatgpt.com/docs/long-running-work)：相关工作尽量留在同一对话共享上下文，只有能够独立执行的任务才拆分到不同对话并行。

关键约束：

- 单张 9:16 图片恰好包含四个有顺序的画面；根据动作选择连续过程或明确切镜。
- 每个镜头不得短于 4 秒，普通产品镜头默认 4 秒，多数镜头保持在 4–10 秒。
- 通常先生成无标签画面，再通过脚本添加时间与动作标签；用户明确要求直接生成标签时检查后不重复添加。
- 保留所有 `storyboard-vNN.png`，不覆盖历史版本。
- 未经用户单独授权，不提交可能收费的视频生成任务。

## 辅助脚本

默认初始化一张、4秒、仅图片的项目：

```bash
python scripts/workflow.py init ./demo-project --name "产品展示"
```

组合交付加 `--delivery storyboard_and_video_prompt`；多张加 `--shots N`。保存提示词与镜头数据并记录审核/快速模式授权后，必须执行 `preflight` 才能调用生图。

命令、版本命名、拆格、冻结、修订、重试与旧项目迁移见 [执行指南](references/execution.md)。不要使用旧版“只有状态、没有文件”的操作示例。

状态写入受跨进程锁与恢复日志保护。批准绑定实际产物哈希，内容变化会使旧批准失效。重做分配新版本，排版拒绝覆盖已有输出。

## 仓库结构

```text
.
├── SKILL.md                  # 主工作流与强制约束
├── agents/openai.yaml        # Codex 展示与调用元数据
├── references/               # 模式、数据结构与提示词模板
├── scripts/                  # 项目协调、排版和预览工具
├── tests/                    # 自动化测试
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
4. 提交变更并创建带注释标签，例如 `git tag -a v1.1.0 -m "Release v1.1.0"`。
5. 推送分支和标签：`git push origin main --follow-tags`。

查看当前版本：

```bash
python scripts/check_release.py
```

## 更新已安装版本

进入安装目录后执行：

```bash
git pull --ff-only
python -m pip install -r requirements.txt
```

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

- [主工作流](SKILL.md)
- [严格分阶段模式](references/strict-mode.md)
- [总控与轻量镜头任务](references/hybrid-coordination.md)
- [项目数据结构](references/schema.md)
- [提示词模板](references/prompt-templates.md)
- [变更日志](CHANGELOG.md)

本 README 的安装位置和发现规则参考了 [OpenAI 官方 skills 文档](https://learn.chatgpt.com/docs/build-skills)。
