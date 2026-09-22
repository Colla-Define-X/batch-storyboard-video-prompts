# Changelog

本项目的显著变更都会记录在此文件中。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/)。

## [Unreleased]

## [1.1.0] - Unreleased

### Added

- 扩展“生成分镜图、设计分镜图、制作视频分镜”等自然语言触发范围。
- 增加默认分阶段与显式快速模式记录、审核批准记录和受控状态转换。
- 发布 schema v4：加入数值时间边界、镜头审核模式与批准历史。
- 增加 schema v3 到 v4 的显式备份迁移命令。
- 增加总控对话、用户选择的镜头并发方式、共享 brief、状态看板与轻量任务指令。
- 增加带用户理由的显式重试命令。

### Changed

- 普通“生成”或“批量生成”不再可能被解释为快速模式。
- 初始化支持自定义时长，并校验最低四秒及四段连续时间。
- 四格清单严格要求四条记录且四个位置各出现一次。
- 收紧 Desktop、CLI、IDE 和跨平台字体兼容性说明。
- 允许每张参考图承担一个或少量明确职责。
- 最终视频提示词改由总控统一生成，镜头任务不再重复公共规则。
- 创建并发任务前必须询问“全部开始”或“先做 1–2 个看效果”，不再默认限制为两个任务。

### Fixed

- 阻止资产 ID 路径越界、重复 ID、无效图片和不支持的文件类型。
- 修正初始化与稳定化参考图的说明顺序。
- 移除严重缺陷自动重试；失败和小问题统一等待用户决定。

## [1.0.0] - 2026-09-21

### Added

- 发布默认分阶段审核与可选快速审核工作流。
- 支持每镜头独立可见任务、三阶段批准与跨镜头并行推进。
- 提供项目初始化、稳定化参考图、状态同步、任务注册和项目校验脚本。
- 提供四宫格确定性排版与可选参考图联系表工具。
- 增加安装、使用、更新、测试和发布说明。
- 建立语义化版本、发布校验、自动化测试与持续集成。

[Unreleased]: https://github.com/Colla-Define-X/batch-storyboard-video-prompts/compare/v1.0.0...HEAD
[1.1.0]: https://github.com/Colla-Define-X/batch-storyboard-video-prompts/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Colla-Define-X/batch-storyboard-video-prompts/releases/tag/v1.0.0
