---
name: batch-storyboard-video-prompts
description: Create or design video storyboard images from product references, grouped images, or shot ideas, including 9:16 four-panel storyboards and matching video prompts. Use when the user asks to 生成分镜图、设计分镜图、制作视频分镜、做四宫格分镜、镜头分组、逐镜头审批或批量生成视频提示词. Default to staged review; use fast mode only when the user explicitly asks to skip or consolidate review.
---

# Batch Storyboard Video Prompts

Create product storyboards using the user's photos and [prompt reference](references/prompt-templates.md). Before operating project files or generating an image, read [execution.md](references/execution.md) for the commands and artifact contract.

## Scope and review mode

- Quantity omitted means **one storyboard image**, regardless of the number of reference photos. One image contains four panels; four panels do not mean four separate deliverables.
- One image stays in the current conversation. Do not ask about concurrency or create another task. For two or more, use separate tasks only after the user chooses that arrangement; then read [hybrid-coordination.md](references/hybrid-coordination.md). All images may also stay here.
- If only images are requested, use `storyboard_only`. Include video prompts only when requested or already accepted, using `storyboard_and_video_prompt`. Scope determines completion.
- Default to staged review: prompt → image → video prompt only for combined delivery. Ordinary “生成分镜图” does not waive prompt review.
- Explicit “直接生成 / 不用确认 / 跳过审核 / 一次出完 / 合并审核 / 快速模式” permits fast mode with combined final review. Record `set-mode ... fast --reason`. Fast mode takes precedence over single-image staged steps. If the user only approves the current prompt, record that approval without changing remaining review gates.

## Brief and references

Defaults: one image, 9:16 canvas, 2×2 equal panels, 4 seconds, 0–1 / 1–2 / 2–3 / 3–4 seconds, top left → top right → bottom left → bottom right, 1080p target, no dialogue or narration. Minimum duration is 4 seconds; typical range is 4–10 seconds. Preserve approved timing, including valid custom ranges.

Confirm scene, duration, audio, scope and reference roles. For a single staged image, combine settings, reference previews and the complete saved prompt in one review message when information is sufficient. Do not repeatedly confirm the same settings. Authorized fast mode uses the user's settings and reasonable defaults without an extra preliminary approval gate.

Stabilize photos under `sources/` using `add-source`. Directly embed original references with absolute local Markdown paths, followed by image IDs and narrow roles. Product photos control identity, structure, color, material and accessories; format images control only layout, photography and labels. Never invent a missing format image. Contact sheets are optional when requested or direct embeds cannot be displayed.

Priority: explicit user text → product reference → scene/light reference → action/composition reference → defaults. Do not invent unseen structures or functions. Substitute another angle or material detail if opening or hand operation is unsuitable.

## Mandatory saved prompt

Every generation requires `shots/<shot-id>/storyboard-prompt.md`, broadly following the user's template in [prompt-templates.md](references/prompt-templates.md). Read that reference for every prompt. Include actual reference roles, layout, photography, four timed states, product constraints, labels and output requirements.

If absent, silently write the file before generating. Restoring approved chat text should preserve it exactly; a new or materially changed prompt needs staged approval. Fast mode permits the draft to remain undisplayed. Saving a file or user silence does not constitute approval.

Populate four panel records, camera plan, product constraints and `sequence_type` (`continuous` or `cuts`) in `shot.json`. Continuous actions must physically connect; different views may use explicit cuts. Do not force opening, hand use, macro details and full-product framing into an implausible single four-second camera move.

After prompt approval or fast-mode authorization, run `preflight <project> <shot-id>` immediately before every image-generation call. It checks saved inputs and reserves one new version. Use the saved prompt for that call. If it fails, do not call generation. Checks cover files, hashes, references and workflow state; the agent still checks prompt quality and visually inspects images.

The saved prompt describes the labeled deliverable. Normally retain its content and append an execution instruction: “Generate clean four-panel artwork without labels or timestamps; reserve label-safe space for later exact typesetting.” Save the actual tool input as `generation-prompt-vNN.md`. If the user explicitly requests generated labels, follow that and do not add duplicate labels afterward.

## Generate and review

1. Staged: save and show complete prompt with references, then record explicit `approve ... storyboard_prompt`. Fast: save prompt, record `set-mode ... fast --reason`, then enter `running`.
2. Run preflight. Generate one image with the image-generation skill and save the allocated `storyboard-vNN.png`. Inspect exactly four panels, product identity/count, structures, hands and action plausibility.
3. For clean art, split the verified grid with the layout helper, populate panel `image` paths and compose `storyboard-review-vNN.png`. Inspect labels and cropping. For directly generated labels, inspect them and save the reviewed image under that review filename. See execution.md.
4. Set `qa.result` to `pass` or `pass_with_notes` only after visual inspection. Severe defects enter failure state and require the user's retry decision. Never retry automatically.
5. Staged: enter `storyboard_review_pending`, present image and QA, wait. Approval freezes the image and hashes. Image-only delivery completes here. Combined delivery continues to `video_prompt_pending`; save `video-prompt.md`, enter `video_prompt_review_pending`, present and wait for approval.
6. Fast: present image and QA, plus a pending video-prompt draft only for combined scope. Enter `review_pending`. `approve ... review_package` freezes and completes. Do not describe a pending image as approved.

Do not automatically submit paid video generation. Video prompts use the matching storyboard as `@Image1`, not an exact first frame, read its panels in order and ignore labels/grid/timestamps. Match the approved sequence type, timing, camera, constraints and actual uploaded image numbering.

## Changes, failures and writes

- Changing prompt, reference, timing, brief or shot plan makes the old binding stale. Use `revise ... storyboard_prompt --reason`, edit, then reapprove in staged mode. Fast mode still needs recorded authorization.
- Explicitly requested new attempts from review/failure use `retry ... --reason`. Reopen approved images with `revise ... storyboard --reason`; staged video-only changes use `revise ... video_prompt --reason`. Preserve all old versions and approval history. Failure phase controls retry destination.
- Never manually edit statuses/approvals. Workflow commands serialize updates to both manifests and recover interrupted transactions. One owner edits a shot's content while idle. Do not remove a lock/journal to bypass a busy command.
- Schema-v3 projects need explicit `migrate`, which backs up changed manifests and resets unbound approvals to pending. Old v4 approvals lacking hashes need revision and renewed approval before further generation; never fabricate retrospective approval.

See [schema.md](references/schema.md) for fields and [strict-mode.md](references/strict-mode.md) for staged review. These commands cannot intercept an agent that directly calls a generation tool without using them; mandatory preflight remains an agent execution requirement.
