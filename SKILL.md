---
name: batch-storyboard-video-prompts
description: Quickly turn grouped product references into parallel, independently reviewed 9:16 four-panel storyboards and matching video prompts. Use for 镜头分组、四宫格分镜、逐镜头审批、可见镜头任务、或批量视频提示词.
---

# Batch Storyboard Video Prompts

Default to a customer-facing staged workflow. Confirm the project globally, create one visible Codex task per shot, and require separate approval for the storyboard prompt, storyboard image, and video prompt. Use the one-pass fast workflow only when the user explicitly asks for fast or consolidated review.

## Confirm once at project level

Present and confirm together:

- compact global configuration: ratio, 2x2 layout, duration, time ranges, visual continuity, audio, review format, delivery scope;
- complete shot-to-image mapping;
- one narrow role per reference: product identity, structure/count, packaging/text, background/lighting, hand/action, or composition.

Defaults: 9:16, 2x2, 5 seconds, top-left → top-right → bottom-left → bottom-right, 1080p, no dialogue or narration. Every shot must be at least 4 seconds; most shots should be 5–10 seconds. Derive four readable time ranges from the approved duration instead of forcing fixed timestamps.

After confirmation, stabilize sources in `sources/`, record hashes, and initialize with `scripts/workflow.py init`. Read [references/schema.md](references/schema.md) only when creating or updating project files.

Conflict precedence: user text; product reference; scene/light reference; action/composition reference; defaults.

## Default customer workflow

After global settings are approved, generate the complete set of shot-specific storyboard prompts. Then, with explicit authorization to create the visible tasks, create one user-visible Codex task per shot and register its task ID. Each task owns one shot and advances through these approval gates:

1. Show the shot's reference-image preview, image IDs, and narrow roles; then present the complete storyboard-generation prompt and wait for approval or modification.
2. Generate, QA, and label the 2x2 storyboard; present it and wait for approval or modification.
3. Freeze the approved storyboard, draft the matching video-generation prompt, and wait for approval or modification.
4. Mark the shot complete only after the video prompt is approved.

Do not skip a gate, infer approval from silence, or generate the next-stage artifact before approval. A change to an earlier stage invalidates and refreshes every dependent later stage. Shots are independent and may progress in parallel without blocking one another. Read [references/strict-mode.md](references/strict-mode.md) before starting shot tasks.

Before presenting a shot prompt, embed each stabilized original reference from `sources/` directly with an absolute local Markdown image path, followed immediately by its image ID and narrow role. Do not generate or compose a derived preview by default: direct embeds are faster, preserve the original pixels, and avoid unnecessary processing. Never require the user to identify references from IDs or filenames alone. Use `scripts/reference_preview.py` only when the user explicitly requests a contact sheet or the host cannot display multiple direct image embeds.

The coordinator owns `project.json`, source stabilization, visible-task creation, and the dashboard. Each shot task writes only inside `shots/<shot-id>/` and owns its `shot.json`. Register visible task IDs with `workflow.py register-task`; sync summaries with `workflow.py sync`.

## Optional fast workflow

Use only when the user explicitly requests fast, consolidated, or one-pass review. Each shot then runs end-to-end before asking for approval:

1. Write a compact shot brief inside `shot.json`: reference roles, four timed states, camera motion, must-keep items, and forbidden changes.
2. Generate one unlabeled 9:16 2x2 storyboard with the image generation skill.
3. Run only the essential QA checks: exactly four panels; correct product count/identity; no severe hand or object deformation; action continuity; no watermark, subtitle, or obvious extra object.
4. Retry once only for a severe objective defect. Report minor composition or packaging-text drift instead of automatically regenerating.
5. Add deterministic labels in the form `time + short Chinese action` with `scripts/storyboard_layout.py`.
6. Draft the matching video prompt from the actual storyboard result.
7. Present one review package: compact brief, labeled storyboard, four-row description table, short QA result, and video prompt.

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
