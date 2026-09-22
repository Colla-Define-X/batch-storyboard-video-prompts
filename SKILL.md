---
name: batch-storyboard-video-prompts
description: Create or design video storyboard images from product references, grouped images, or shot ideas, including 9:16 four-panel storyboards and matching video prompts. Use when the user asks to 生成分镜图、设计分镜图、制作视频分镜、做四宫格分镜、镜头分组、逐镜头审批或批量生成视频提示词. Default to staged review; use fast mode only when the user explicitly asks to skip or consolidate review.
---

# Batch Storyboard Video Prompts

Default to a customer-facing staged workflow. Requests such as “生成分镜图”, “设计分镜图”, “制作视频分镜”, or “批量生成分镜” select this skill but do not select fast mode. Confirm the project globally and require separate approval for the storyboard prompt, storyboard image, and video prompt.

Use the one-pass fast workflow only when the user explicitly asks for “直接生成”, “不用确认”, “跳过审核”, “一次出完”, “合并审核”, “快速模式”, or an equivalent unambiguous instruction. Record that request with `workflow.py set-mode ... fast --reason`. If the wording is ambiguous, remain staged.

## Confirm once at project level

Present and confirm together:

- compact global configuration: ratio, 2x2 layout, duration, time ranges, visual continuity, audio, review format, delivery scope;
- complete shot-to-image mapping;
- one or a small number of narrow roles per reference: product identity, structure/count, packaging/text, background/lighting, hand/action, or composition. Keep the role set minimal.

Defaults: 9:16, 2x2, 5 seconds, top-left → top-right → bottom-left → bottom-right, 1080p, no dialogue or narration. Every shot must be at least 4 seconds; most shots should be 5–10 seconds. Derive four readable time ranges from the approved duration instead of forcing fixed timestamps.

After confirmation, initialize the empty project with `scripts/workflow.py init`, fill the generated `shared-brief.md` once, then add each source with `workflow.py add-source` so it is stabilized under `sources/` with a recorded hash. Read [references/schema.md](references/schema.md) only when creating or updating project files.

Conflict precedence: user text; product reference; scene/light reference; action/composition reference; defaults.

## Default customer workflow

After global settings are approved, generate the complete set of shot-specific storyboard prompts. Before creating any parallel shot conversations, ask the user to choose between starting every shot now or piloting one or two shots to review the effect first. Do not infer either choice or create shot conversations before the answer. Record the choice with `workflow.py set-concurrency`, then create only the authorized tasks. Read [references/hybrid-coordination.md](references/hybrid-coordination.md) before creating shot tasks.

If the user prioritizes minimum usage over true background parallelism, keep every shot in the coordinator conversation. Shots may remain at different states, but disclose that one conversation does not provide independent background execution. If the host cannot create visible tasks, use this single-conversation workflow.

Each shot task or in-conversation shot advances through these gates:

1. Show the shot's reference-image preview, image IDs, and narrow roles; then present the complete storyboard-generation prompt and wait for approval or modification.
2. Generate, QA, and label the 2x2 storyboard; present it and wait for approval or modification.
3. Freeze the approved storyboard and return control to the coordinator. The coordinator drafts matching video prompts, preferably in one batch, and waits for approval or modification.
4. Mark the shot complete only after the video prompt is approved.

In staged mode, do not skip a gate, infer approval from silence, or generate the next-stage artifact before approval. Record approvals with `workflow.py approve`. A change to an earlier stage invalidates and refreshes every dependent later stage. Shots are independent and may progress in parallel without blocking one another. Generate the dashboard with `workflow.py dashboard` instead of repeating project context. Read [references/strict-mode.md](references/strict-mode.md) before starting shot tasks.

Before presenting a shot prompt, embed each stabilized original reference from `sources/` directly with an absolute local Markdown image path, followed immediately by its image ID and narrow role. Do not generate or compose a derived preview by default: direct embeds are faster, preserve the original pixels, and avoid unnecessary processing. Never require the user to identify references from IDs or filenames alone. Use `scripts/reference_preview.py` only when the user explicitly requests a contact sheet or the host cannot display multiple direct image embeds.

The coordinator owns `shared-brief.md`, `project.json`, source stabilization, the concurrency question, visible-task creation, the dashboard, and final video prompts. Each shot task reads the shared files, writes only inside `shots/<shot-id>/`, and owns its `shot.json`. Give it only the output of `workflow.py task-brief`; do not paste the complete global brief into its prompt. Register visible task IDs with `workflow.py register-task`, release a slot with `workflow.py release-task`, and sync summaries with `workflow.py sync`.

## Optional fast workflow

Use only when the user explicitly requests fast, direct generation, skipped confirmation, consolidated review, or one-pass review. Ordinary uses of “生成” or “批量生成” are not enough. Before generating, set the shot to fast mode and record the user's request. Each shot then runs end-to-end before asking for approval:

1. Write a compact shot brief inside `shot.json`: reference roles, four timed states, camera motion, must-keep items, and forbidden changes.
2. Generate one unlabeled 9:16 2x2 storyboard with the image generation skill.
3. Run only the essential QA checks: exactly four panels; correct product count/identity; no severe hand or object deformation; action continuity; no watermark, subtitle, or obvious extra object.
4. Never retry automatically. Report severe failures and minor composition or packaging-text drift, set the relevant failure or review status, and wait for the user. Retry only through `workflow.py retry ... --reason` after an explicit request.
5. Add deterministic labels in the form `time + short Chinese action` with `scripts/storyboard_layout.py`.
6. Return the actual storyboard and QA result to the coordinator.
7. The coordinator drafts the matching video prompt and presents one review package: compact brief, labeled storyboard, four-row description table, short QA result, and video prompt.

Set `review_pending` and wait. The user may approve, request a targeted change, or request regeneration. On approval, preserve the accepted version as `storyboard-final.png`, keep the final video prompt, and mark `complete`. A storyboard change requires refreshing its video prompt.

Do not infer approval from silence. Approval applies only to that shot.

Read [references/prompt-templates.md](references/prompt-templates.md) when composing the review package or video prompt.

## Core invariants

- One 9:16 image contains exactly four coherent panels.
- Keep product count, identity, geometry, materials, patterns, packaging layout, hands, lighting, and final state stable.
- Treat packaging text as visual layout; do not promise exact unreadable small copy or add marketing text.
- Generate without labels, then add labels deterministically.
- Preserve numbered versions; never overwrite `storyboard-vNN.png`.
- `@Image1` in the video prompt is the approved storyboard reference, not an exact first frame. Tell the video model to read the four panels in order and ignore grid lines, labels, timestamps, and instructional text.
- Avoid flicker, morphing, duplicated parts, drifting patterns, extra fingers, subtitles, and watermarks.
- Do not submit paid video generation unless the user separately asks.

## Duration invariant

- Reject or revise any proposed shot shorter than 4 seconds.
- Default ordinary product shots to 5 seconds.
- Keep most shots within 5–10 seconds; use 4 seconds only for a deliberately concise transition or detail beat.
- Reflect the approved duration consistently in the storyboard prompt, panel labels, shot manifest, and video prompt.
