# Roadmap

本文件保存尚未进入当前运行流程的后续版本提案。除非某个提案被正式实现、测试并写入 `SKILL.md`，否则不应把它视为现行行为。

## 单对话、本地文件驱动模式

状态：已暂存，暂不实施
目标版本：后续独立版本，版本号待定
当前优先级：先打磨现有分阶段审核、提示词、分镜生成与交付细节

### 目标

让多个镜头在同一个对话中保持独立状态，通过本地文件恢复项目事实和当前工作集，减少重复加载公共背景与重复输出长提示词。该模式优化上下文使用，但不承诺多个镜头像独立任务一样在后台并行。

### 拟议模式选择

项目先选择执行方式：

- `single_conversation`：全部镜头由当前对话协调，不创建镜头任务，也不询问并发数量；
- `multi_task`：使用独立镜头任务，随后再询问“全部开始”或“先做 1–2 个看效果”。

用户未选择时不推断执行方式。

### 拟议文件职责

```text
project/
  shared-brief.md
  project.json
  current-context.md
  sources/
  shots/
    shot-01/
      shot.json
      storyboard-prompt.md
      qa-v01.md
      video-prompt.md
```

- `shared-brief.md`：只保存项目级视觉、声音、连续性和禁止项；
- `project.json`：保存执行模式、公共配置和镜头状态摘要，不保存大段提示词；
- `shot.json`：保存单个镜头状态、引用、时间段、审核、重试和版本信息；
- 镜头 Markdown 文件：保存完整提示词和 QA，按需读取；
- `current-context.md`：由脚本生成，只列当前可执行、等待确认、失败暂停和已完成的镜头及所需文件路径。

### 拟议命令

```bash
python scripts/workflow.py set-execution PROJECT single
python scripts/workflow.py set-execution PROJECT multi
python scripts/workflow.py next-actions PROJECT
python scripts/workflow.py context PROJECT
python scripts/workflow.py hold PROJECT SHOT_ID --reason "用户决定暂不继续"
```

命令意图：

- `set-execution`：记录单对话或多任务模式；
- `next-actions`：按各镜头状态分组输出可继续、待确认、暂停和已完成事项；
- `context`：生成最小当前工作集，避免读取全部镜头长文本；
- `hold`：明确记录暂不继续且不自动重试。

### 必须保留的现有约束

- 普通“生成”不等于快速模式；
- 用户未明确要求时不得跳过审核；
- 每个镜头保持独立状态和审核记录；
- 失败后不得自动重试；
- 视频提示词必须依据已确认分镜；
- 参考图、时长和恰好四格的校验继续生效；
- 历史版本不得被覆盖。

### 实施前需要确认

- 单对话是否作为推荐模式，还是只作为节省上下文的可选模式；
- 执行模式是在项目初始化时询问，还是准备创建镜头任务时询问；
- `current-context.md` 是持久化文件还是按命令临时输出；
- 一轮最多推进多少个已获批准的镜头；
- 用户的自然语言批量审批如何映射为确定性的多镜头状态更新；
- 是否需要从 schema v4 升级 schema，及旧项目迁移策略。

### 验收标准草案

- 单对话模式不要求设置并发槽位，也不能注册外部镜头任务；
- 重新打开项目后，仅靠本地文件可以恢复所有镜头的真实状态；
- 最小上下文不复制完整公共 brief 或无关镜头提示词；
- 同一轮可以分别批准、暂停、修改或继续不同镜头；
- 早期阶段发生修改时，所有依赖的后续产物会失效；
- 单对话模式不会被描述成真实后台并行；
- 新行为有命令级测试、迁移测试和真实多镜头流程测试。

### 当前不做

- 不修改 schema；
- 不增加上述命令；
- 不改变当前总控与镜头任务流程；
- 不把单对话模式设为默认；
- 不修改当前版本号或发布范围。
