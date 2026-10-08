# Project schema and artifact contract

The JSON schema remains version 4. Hardened commands add content bindings and delivery scope. New initial projects have `workflow.handoff_model: prepared_prompt_to_shot`; its absence on an existing project keeps the earlier handoff. This is an ownership marker, not a new authorization system. Old v4 approvals without bindings are not silently trusted; use revise and renew approval. Legacy v3 migration is explicit and does not add the handoff marker.

## Project defaults

`workflow.py init PROJECT --name NAME` creates one storyboard, 4 seconds, and `delivery_scope: storyboard_and_video_prompt`. Use `storyboard_only` only after the user explicitly declines a video prompt. Older files without this field retain their original combined scope.

Scope is project-wide. `save-content` rejects a changed scope while any shot has a pending prompt review, prompt/artifact approval history, generation binding/version, or an advanced state. A submitted but never-approved prompt review can be withdrawn with `revise storyboard_prompt`; if all shots are back in drafting and none has approval or generation history, an early scope change remains allowed. Withdrawing an approval does not erase its history. The image-binding format remains unchanged for compatibility. Mid-project scope conversion is not supported; explain that limitation instead of erasing history or regenerating an image to bypass it.

New projects also create `content-plan.json` and set `workflow.content_plan_required: true`. For new multi-shot staged use, the coordinator fills it after confirming the creative design, then saves every complete initial prompt and corresponding shot content and records every `check-prompt-plan` before choosing concurrency or creating a shot task. Initial `set-concurrency` and each first task registration require current complete prepared inputs in `storyboard_prompt_pending`, not prior user approval of the prompt. Single and fast shots use the current conversation. Existing projects without `handoff_model` keep the original child-drafts/coordinator-checks-and-approves/video route, even if concurrency has not yet been chosen. Existing projects without `content_plan_required` continue their prior review path. For a single image, use `relationship: single`; for multiple images use `continuous` or `independent`. `content_type` is `story`, `showcase`, or `mixed`. A showcase can communicate packaging, structure, detail or function without an invented character story.

```json
{
  "content_type": "showcase",
  "relationship": "independent",
  "approval_source": "user",
  "confirmation": "用户对整批逐张设计的实际确认",
  "shots": [
    {
      "shot_id": "shot-01",
      "confirmation": "用户对这一张四格设计的实际确认",
      "context": "桌面产品展示",
      "primary_selling_point": "包装质感",
      "purpose": "展示整体与材质",
      "panel_beats": ["展示包装整体", "展示开盖后的陈列", "展示表面细节", "展示包装与产品的关系"],
      "shot_scales": ["wide", "medium", "macro", "close"],
      "opening_motif": "包装整体出现",
      "action_motif": "开盖观察陈列",
      "ending_motif": "包装与产品同框",
      "avoid_repeating": ["其他分镜的再次开箱"],
      "intentional_bookend": false
    }
  ]
}
```

The example shows one shot entry; an actual file must contain exactly one ordered entry for every project shot. Confirmation text is only a readable summary, never authorization by itself. Before showing each design, run `prepare-design-review`; record the reply with `approve-design --review-id ID --confirmation TEXT`. Commands save the creative snapshot and its hash in the shot manifest. Changing the design makes its approval stale, even when old confirmation text remains. The top-level confirmation is an optional batch summary.

`shot_scales` uses `wide`, `medium`, `close`, or `macro` in panel order. Default to at least three distinct scales; fewer require a nonempty text `scale_exception_reason`. `intentional_bookend`, when supplied, must be a JSON boolean, not a string or number. Identical opening and ending motifs require `true` and a nonempty text `bookend_reason` explaining the visible change. An exact repeated opening/action/ending combination across shots is rejected; the responsible conversation must also assess semantic similarity, which a string check cannot prove. For explicit fast requests, first record fast mode, use `approval_source: explicit_fast_request`, and internally bind the design using the same commands and the actual skip request without a visible creative checkpoint. Plain “生成” is not an explicit fast request.

Design snapshots include global content type/relationship, resolved approval source and this shot's creative fields, not mutable confirmation summaries. Batch concurrency selection validates all entries; local execution validates only the current entry and common dependencies. Other shots' unfinished draft fields do not block it. Global design changes stale all affected approvals. New approvals also check the last non-retired approved action arcs of other shots, even if their drafts are unfinished. For explicit grouped changes, `revise-designs` retires the selected design approvals together with `invalidated_at`; historical assignments no longer reserve arcs, but still remain in history. In the new handoff, a child may revise its own approved assignment after `revise storyboard_prompt` by whole-file versioned read/merge/save of `content-plan.json`, changing only its own entry, then renewing this shot's design confirmation, plan check and prompt review. This is the existing CAS save contract, not per-entry locking or permission enforcement; shared/global or cross-shot changes still require coordination. Existing projects without `content_plan_required` retain the legacy route; earlier local planning projects with only text confirmations must renew approval, not silently fabricate hashes.

An entry may override `approval_source` when only that shot changes review mode. For example, when revising a previously fast shot to staged review, set that entry to `user` and record its new creative confirmation; other fast shots retain their explicit authorization.

- `defaults.ratio`: `9:16`; `layout`: `2x2`.
- `duration_seconds`: finite number >= 4, usually 4–10.
- `time_boundaries_seconds`: exactly five finite increasing values starting at 0 and ending at duration. Default `[0,1,2,3,4]`. Custom approved ranges are valid.
- `time_ranges`: display strings derived from those values; keep all shot panels consistent.
- `workflow.execution_model`: initially `current_conversation`; authorized multi-shot concurrency changes it to `coordinator_with_shot_slots`.
- `workflow.handoff_model`: new init writes `prepared_prompt_to_shot`. Only multi-shot staged shots use its new handoff; single-shot and fast shots remain in the current conversation. Existing projects without it, including migrated v3, retain their old staged multi-shot ownership. Unknown values are rejected; do not infer or backfill the marker from the shot count or launch choice.
- `workflow.video_prompt_owner`: initially `current_conversation`; choosing concurrency sets `shot_task` for the new marked handoff or `coordinator` for an unmarked legacy project. It describes the working route, not an ACL. Single and fast shots remain local even when a mixed project's owner is `shot_task`.
- `parallel_launch_mode` / `max_parallel_shot_tasks`: null until an authorized multi-shot choice. Single-shot projects cannot register separate tasks.
- `pilot_shot_ids`: the first distinct IDs registered in the current pilot round; at most the selected count. Release/completion does not remove IDs. Same-shot reactivation is allowed; other IDs need a new user decision. A changed choice requires `set-concurrency --reason` and is recorded in `launch_history`. Legacy pilot choices without a cohort must be renewed explicitly.
- `shared_brief_path`: project-relative Markdown path.
- `shots`: unique safe IDs and summary status, mode and task registration. Workflow commands update summaries together with shot records.

## Shot content

Each `shots/shot-01/shot.json` has `shot_id` matching its folder. IDs use lowercase letters/digits separated by single hyphens; resolved paths stay within the project.

Fill content before approval:

```json
{
  "references": [{"id":"image-01","roles":["product_identity","structure_count"]}],
  "review_style": "木桌暖光写实产品摄影",
  "review_context": "桌面产品展示",
  "review_selling_point": "包装质感",
  "review_purpose": "展示整体与材质",
  "sequence_type": "cuts",
  "camera": "包装全景切到开盖陈列中景，再切表面微距，最后以近景展示包装与产品的关系",
  "must_keep": ["产品数量与配件结构"],
  "forbidden": ["增加配件"],
  "panels": [
    {"plan_panel_id":"shot-01:panel-1","shot_scale":"wide","position":"top_left","start_seconds":0,"end_seconds":1,"time":"0–1秒","label":"外观展示","description":"展示包装整体"},
    {"plan_panel_id":"shot-01:panel-2","shot_scale":"medium","position":"top_right","start_seconds":1,"end_seconds":2,"time":"1–2秒","label":"开盖陈列","description":"展示开盖后的陈列"},
    {"plan_panel_id":"shot-01:panel-3","shot_scale":"macro","position":"bottom_left","start_seconds":2,"end_seconds":3,"time":"2–3秒","label":"材质细节","description":"展示表面细节"},
    {"plan_panel_id":"shot-01:panel-4","shot_scale":"close","position":"bottom_right","start_seconds":3,"end_seconds":4,"time":"3–4秒","label":"产品同框","description":"展示包装与产品的关系"}
  ]
}
```

`sequence_type` is `continuous` or `cuts`. Replace generic descriptions with actual product-specific visible states. Save content patches via `save-content` with the version from `content-revision`; statuses and approval fields are rejected. Panel `image` paths are added after generation, relative to the shot folder. Changing an image path alone does not invalidate prompt approval; changing the panel description or label does. During generation the save command permits only QA and image-path changes; revise before editing other approved content. Image/package review additionally permits QA-only patches, not panel paths or creative fields. Changed QA clears `artifact_review`; unchanged QA preserves it. Minor updates retain the pending state and image, while `failed` atomically moves to the existing failure state as described below. Staged video review and complete states do not gain QA editing permission.

For planned projects, `review_context`, `review_selling_point`, `review_purpose` must exactly match the approved entry's context, primary selling point and purpose. Panels must be in reading order; their fixed `plan_panel_id`, `description` and `shot_scale` must match the corresponding approved beat and scale. Keep technical elaboration separate (for example `technical_detail` or additional prompt prose). Full prompts include these core fields and the Chinese scale names 全景/中景/近景/微距. These checks do not prove semantic consistency of all free text; the coordinator performs the new handoff's initial batch review, and the shot conversation checks its own later local revisions.

Reference roles should be narrow: product identity, structure/count, packaging/text, background/light, hand/action, or composition. A format reference has only format/style/label roles. Every referenced ID must exist in the stabilized assets list, with a verified source hash.

## Required artifacts and records

```text
project.json
content-plan.json             # new projects
shared-brief.md
sources/image-01.jpg
shots/shot-01/
  shot.json
  storyboard-prompt.md
  generation-prompt-v01.md
  storyboard-v01.png
  panels/panel-v01-01.png ... panel-v01-04.png  # only when splitting panels for local typesetting
  storyboard-review-v01.png
  storyboard-final.png
  storyboard-final.json
  video-prompt.md                 # combined scope only
```

- `storyboard-prompt.md`: complete final-deliverable specification, required before generating.
- `review_style` and `review_selling_point`: concise user-facing statements for the current shot. The full prompt must contain these statements and each panel's time, label and description verbatim, with technical instructions added around them.
- `prompt_review`: `prepare-prompt-review` records the current input binding, summary hash, and a unique submission ID; its output is shown in chat with a link to the complete prompt file. In the new multi-shot staged handoff, first register the real shot task; without a recorded thread ID this command rejects initial review. It does not require an active generation slot, so an existing child can review a later revision after its slot was released. Each resubmission has a new ID even for identical content; valid reviews are not prepared again merely to resume a task.
- `artifact_review`: entering an image, video-prompt or package review state records its stage, unique ID, artifact binding, QA hash and timestamp. New artifact approvals require that ID and the user's subsequent confirmation. Changed video text clears this record; `prepare-artifact-review` resubmits the current version before it is shown again. A new submission has a new ID even if the bytes are identical. Old completed approvals remain checked by their original bindings; old pending reviews without this record must be prepared and shown anew.
- `design_review` / `design_approvals`: command-maintained creative review snapshot, hash, unique submission ID, actual confirmation and timestamp. Keep approval history; never write these manually. Editing text summaries is not approval. `revise-designs` retires selected old approvals, clears old review IDs and records the selected IDs and user reason in `revisions`. Resubmitting an identical design uses a new ID and needs that submission's confirmation; existing valid approvals are not rewritten.
- `plan_check`: `check-prompt-plan --note ...` stores the responsible conversation's semantic-check note with the current input binding. In the new handoff, the coordinator checks all initial prompts; each child checks its own later local revisions. Single/fast shots stay local and unmarked legacy multi-shot projects retain coordinator checking. Required for planned staged and fast shots; changed inputs require another check. It is internal bookkeeping, not a user checkpoint.
- `approvals`: new staged prompt approvals record the review ID and the user's confirmation text alongside the content binding. The CLI checks their current file binding, while the agent must verify the reply follows the review and targets this shot. Existing approvals without review IDs remain valid until revised. Revisions mark affected entries `invalidated_at`; never erase history.
- `generation_binding`: input snapshot (prompt, brief, settings/scope, shot plan, panel semantics and reference hashes).
- `generation_claimed`: preflight reserves one invocation; calling it twice without retry/revision fails.
- A claimed generation cannot be reset by revision while its execution state has no valid review image for the allocated version and passing QA. This completion check is independent of current input validity, so a finished result under superseded inputs can enter user-requested prompt/design revision. It does not authorize approval or another generation: those still validate current inputs and approvals. The flag remains true for finished results and is not a live-job flag. Recording an actual failure preserves the original binding/version even if current dependencies are stale. Failure does not cancel an external call.
- `storyboard_version`: allocated by preflight from existing numbered image versions.
- `qa`: actual visual result `pass` or `pass_with_notes` plus notes for review; do not set pass without inspecting the image. QA-only saves during image/package review allow `pass`, `pass_with_notes`, or `failed`, with a list of strings if `notes` is supplied; reject `not_run` and invalid values there. A failed update changes `storyboard_review_pending` to `generation_failed` (`failed_from: storyboard_generating`), or `review_pending` to `failed` (`failed_from: running`), clears the artifact review, invalidates downstream approvals, and updates the project summary in the same transaction. It preserves numbered images, version, generation binding and claimed flag, and grants no retry.
- Image approval binds the input snapshot, version and review image hash. Freeze writes matching PNG and JSON automatically.
- Video approval binds the frozen image and nonempty `video-prompt.md` hash. Fast package approval binds image and optional video according to scope.
- New image/video/package approvals also record `artifact_review_id` and the actual confirmation. These use the existing user checkpoints, not additional questions.
- `failed_from`, `retries` and `revisions`: command-maintained phase and user reasons.

## States

Staged image-only:

```text
todo -> storyboard_prompt_pending --prepare-prompt-review / user confirmation / approve--> storyboard_generating
     --preflight / image generation / QA--> storyboard_review_pending
     --approve and freeze--> complete
```

Combined scope: image approval instead enters `video_prompt_pending`; save video text, enter `video_prompt_review_pending`, then approve to complete. For a new marked multi-shot staged project, image approval clears `task.active` but retains thread/host identity, and the same child continues video review and delivery without re-registration or preflight. An explicit image-only scope instead completes at image approval. Unmarked legacy projects retain coordinator video ownership.

Fast: explicit mode reason, then `todo -> running -> review_pending --approve review_package--> complete`. The preflight and artifacts remain required. Mode can switch at todo or prompt-pending; later changes use revise rather than forcing an illegal state.

Normal status transitions cannot restart generation. Retry requires a user reason and returns only to the failed phase or the currently reviewed artifact's generation phase. Revisions invalidate only the affected stage and downstream approvals.

Within `storyboard_prompt_pending`, `task-brief` distinguishes prepared content, needed local checking, awaiting confirmation (current bound review), and stale review (inputs changed). New-model first handoffs require complete current inputs and wait for real task registration before review. An already assigned child can resume its own incomplete or unapproved creative revision with local design confirmation instead of being sent back to the coordinator. A valid review never instructs the task to rewrite or replace its review ID. A stale review requires checking changes and resubmission, not reusing an old reply. Legacy drafting keeps its original route.

For artifact review states, `task-brief` reports whether the artifact review is current or needs resubmission. Fast video-only revision clears the old package review and preserves the image; save the new text, prepare the artifact review, show it and obtain a new confirmation without preflight. New multi-shot staged preflight checks the current all/pilot launch scope and matches caller `thread_id` / `host_id` to the existing active task registration before allocating a version. Both host values may be absent; a registered host must match exactly. No new schema fields are required. Single and fast shots need no caller identity; downstream validation of finished images does not require an active task or membership in a later pilot round.

## Persistence and migration

Workflow mutations and `save-content` lock the complete project read/modify/write operation. The format-2 rollback journal records a file immediately before its actual write, storing its original bytes and attempted content hashes. Recovery restores only those files, never unrelated shot drafts. A conflicting out-of-band write stops recovery without overwriting it; preserve both current files and the journal for manual reconciliation. Legacy journals lack per-write evidence and require explicit recovery rather than automatic broad rollback.

`content-revision` returns the current file SHA-256 or `missing`; capture this before reading and drafting. `save-content --from-file DRAFT --expected-hash HASH` rejects a changed version under the same lock. On conflict, reread and merge, never simply substitute a new hash for the stale draft. Shot JSON drafts are allowlisted content patches; project JSON patches permit only name/defaults/delivery scope. Plans and Markdown are whole-file drafts. All mutable project content uses this path; separate numbered media and actual generation-input logs remain versioned artifacts. Workflow states/approvals must still use their dedicated commands.

`migrate` accepts v3, creates project.json.bak and each shot.json.bak, preserves valid old time boundaries and sources, and archives unbound approval history as invalidated. Previously advanced shots return to prompt-pending; legacy status is retained for reference. It does not invent current approval hashes or add the new handoff marker. Failure rolls back the entire migration including new backups.

`validate` checks artifacts and bindings in advanced states; incomplete todo/prompt-pending content may remain unfinished. It normally reads without changing project content, but first recovers an interrupted transaction if a journal exists. It cannot evaluate product semantics or prove image quality; visual QA remains required.

See [execution.md](execution.md) for the command sequence.
