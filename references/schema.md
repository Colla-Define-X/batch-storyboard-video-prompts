# Project schema and artifact contract

The JSON schema remains version 4. Hardened commands add content bindings and delivery scope. Old v4 approvals without bindings are not silently trusted; use revise and renew approval. Legacy v3 migration is explicit.

## Project defaults

`workflow.py init PROJECT --name NAME` creates one storyboard, 4 seconds, and `delivery_scope: storyboard_only`. Combined scope is `storyboard_and_video_prompt`. Older files without this field retain their original combined scope.

- `defaults.ratio`: `9:16`; `layout`: `2x2`.
- `duration_seconds`: finite number >= 4, usually 4–10.
- `time_boundaries_seconds`: exactly five finite increasing values starting at 0 and ending at duration. Default `[0,1,2,3,4]`. Custom approved ranges are valid.
- `time_ranges`: display strings derived from those values; keep all shot panels consistent.
- `workflow.execution_model`: initially `current_conversation`; authorized multi-shot concurrency changes it to `coordinator_with_shot_slots`.
- `parallel_launch_mode` / `max_parallel_shot_tasks`: null until an authorized multi-shot choice. Single-shot projects cannot register separate tasks.
- `shared_brief_path`: project-relative Markdown path.
- `shots`: unique safe IDs and summary status, mode and task registration. Workflow commands update summaries together with shot records.

## Shot content

Each `shots/shot-01/shot.json` has `shot_id` matching its folder. IDs use lowercase letters/digits separated by single hyphens; resolved paths stay within the project.

Fill content before approval:

```json
{
  "references": [{"id":"image-01","roles":["product_identity","structure_count"]}],
  "sequence_type": "cuts",
  "camera": "外观到结构特写在1秒切镜；3秒切回完整外观",
  "must_keep": ["产品数量与配件结构"],
  "forbidden": ["增加配件"],
  "panels": [
    {"position":"top_left","start_seconds":0,"end_seconds":1,"time":"0–1秒","label":"外观展示","description":"完整产品位于木桌中央"},
    {"position":"top_right","start_seconds":1,"end_seconds":2,"time":"1–2秒","label":"结构展示","description":"第二展示面及可见连接结构"},
    {"position":"bottom_left","start_seconds":2,"end_seconds":3,"time":"2–3秒","label":"材质细节","description":"真实材质的局部特写"},
    {"position":"bottom_right","start_seconds":3,"end_seconds":4,"time":"3–4秒","label":"产品定格","description":"回到清晰完整的产品外观"}
  ]
}
```

`sequence_type` is `continuous` or `cuts`. Replace generic descriptions with actual product-specific visible states. Do not change statuses or approval records while filling these fields. Panel `image` paths are added after generation, relative to the shot folder. Changing an image path alone does not invalidate prompt approval; changing the panel description or label does.

Reference roles should be narrow: product identity, structure/count, packaging/text, background/light, hand/action, or composition. A format reference has only format/style/label roles. Every referenced ID must exist in the stabilized assets list, with a verified source hash.

## Required artifacts and records

```text
project.json
shared-brief.md
sources/image-01.jpg
shots/shot-01/
  shot.json
  storyboard-prompt.md
  generation-prompt-v01.md
  storyboard-v01.png
  panels/panel-v01-01.png ... panel-v01-04.png
  storyboard-review-v01.png
  storyboard-final.png
  storyboard-final.json
  video-prompt.md                 # combined scope only
```

- `storyboard-prompt.md`: complete final-deliverable specification, required before generating.
- `approvals`: commands append stage, decision, note, timestamp and content `binding`. Revisions mark affected entries `invalidated_at`; never erase history.
- `generation_binding`: input snapshot (prompt, brief, settings/scope, shot plan, panel semantics and reference hashes).
- `generation_claimed`: preflight reserves one invocation; calling it twice without retry/revision fails.
- `storyboard_version`: allocated by preflight from existing numbered image versions.
- `qa`: actual visual result `pass` or `pass_with_notes` plus notes; do not set pass without inspecting the image.
- Image approval binds the input snapshot, version and review image hash. Freeze writes matching PNG and JSON automatically.
- Video approval binds the frozen image and nonempty `video-prompt.md` hash. Fast package approval binds image and optional video according to scope.
- `failed_from`, `retries` and `revisions`: command-maintained phase and user reasons.

## States

Staged image-only:

```text
todo -> storyboard_prompt_pending --approve--> storyboard_generating
     --preflight / image generation / QA--> storyboard_review_pending
     --approve and freeze--> complete
```

Combined scope: image approval instead enters `video_prompt_pending`; save video text, enter `video_prompt_review_pending`, then approve to complete.

Fast: explicit mode reason, then `todo -> running -> review_pending --approve review_package--> complete`. The preflight and artifacts remain required. Mode can switch at todo or prompt-pending; later changes use revise rather than forcing an illegal state.

Normal status transitions cannot restart generation. Retry requires a user reason and returns only to the failed phase or the currently reviewed artifact's generation phase. Revisions invalidate only the affected stage and downstream approvals.

## Persistence and migration

Workflow mutations lock the complete project read/modify/write operation. A rollback journal captures affected control files and final frozen copies; caught failures restore them, and the next command recovers an interrupted process. Public helpers for directly editing files are not concurrency-safe workflow operations. One owner edits each shot's content while idle.

`migrate` accepts v3, creates project.json.bak and each shot.json.bak, preserves valid old time boundaries and sources, and archives unbound approval history as invalidated. Previously advanced shots return to prompt-pending; legacy status is retained for reference. It does not invent current approval hashes. Failure rolls back the entire migration including new backups.

`validate` checks artifacts and bindings in advanced states; incomplete todo/prompt-pending content may remain unfinished. It normally reads without changing project content, but first recovers an interrupted transaction if a journal exists. It cannot evaluate product semantics or prove image quality; visual QA remains required.

See [execution.md](execution.md) for the command sequence.
