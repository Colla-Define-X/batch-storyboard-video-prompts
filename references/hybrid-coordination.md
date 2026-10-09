# Hybrid coordinator and shot-task workflow

Use this reference for staged requests for two or more storyboard images. New projects marked `workflow.handoff_model: creative_plan_to_shot` use the creative-plan handoff below. Existing `prepared_prompt_to_shot` projects retain prepared initial prompts and an explicit all/pilot choice; unmarked projects retain coordinator-led prompt approval and video prompts, as described under compatibility below. Never infer or change a model from shot count, task absence or launch choice. Explicit fast requests stay in the current conversation; follow [execution.md](execution.md). Omitted quantity means one storyboard; keep a single image and all its reviews in the current conversation without task creation or concurrency selection.

Use one coordinator plus all approved staged shot conversations by default for the new model. An explicitly requested pilot limits that launch; it is not the default and not a rolling queue.

This follows [OpenAI's long-running work guidance](https://learn.chatgpt.com/docs/long-running-work): keep related work in one chat for shared context and use separate chats only when tasks can run independently.

## New creative-plan handoff: coordinator ownership

For a new marked multi-shot staged project, the coordinator owns:

- `shared-brief.md` and global visual rules;
- initial `content-plan.json`: the story/showcase decision, verified contexts and selling points, complete six-column panel content and scales, plus cross-shot diversity;
- `project.json`, stabilized sources, task registration, and the dashboard;
- saving each shot's reference IDs and roles, the completed shared brief and approved creative plan before handoff; technical prompts and full production panel data are not initial handoff prerequisites;
- presenting the batch with [creative-review-template.md](creative-review-template.md), then recording all current creative approvals and the default all launch (or the user's explicit pilot) before creating conversations;
- maintaining global settings, source assets and cross-shot coordination when a change genuinely affects more than one shot.

The coordinator does not write the new model's initial technical prompts, routinely submit local prompt reviews, approve images, write video prompts, or aggregate delivery. Each shot conversation owns these steps through completion. Both marked handoffs set `video_prompt_owner: shot_task` on launch; this describes ownership, not a new checkpoint or permission system.

Plan the whole batch before presentation. Resolve whether it forms one continuous video or independent options; show overall progression when applicable. Use the template's batch overview and per-image six-column tables, then seek one explicit batch approval rather than one compulsory reply per image. Save every column in the existing approved beat text and scales; see [schema.md](schema.md). Before presentation, review panel purpose, within-grid progression and semantic cross-shot duplication of openings, actions, endings and evidence. Do not mistake different wording/angles for new content or stable product/lighting identity for unwanted repetition. A local requested change affects only the relevant designs; explain any cross-shot impact before revising others. Plain “生成” stays staged; explicit fast requests use their own internal authorization without these visible checkpoints.

When the user asks for overall progress, read `workflow.py dashboard <project>` on demand. Do not turn it into routine coordinator status collection, per-shot approval relay or final delivery aggregation. Shots do not need to remain synchronized.

Before showing the batch, prepare each unapproved current design with `prepare-design-review` (reuse a still-valid submission on resume). After a scope-clear batch reply, record `approve-design` for every included current ID using that actual reply. Do not treat partial approval as batch approval or silently attach it to changed content. Keep unaffected valid approvals; the ordinary batch launch waits until the whole required plan is approved. A saved confirmation sentence is not authorization. Record `set-concurrency ... all` without an additional all/pilot question, or the explicitly requested pilot. These are internal commands, not extra user checkpoints. See [execution.md](execution.md).

The handoff gives each child the whole batch context, its complete approved design, reference assignments and shared brief. The coordinator verifies project membership, registers the real thread/host and passes that identity. The child waits for registration before initial prompt review; then writes its full prompt and shot content, checks alignment and global repetition with `check-prompt-plan`, and uses [storyboard-prompt-review-template.md](storyboard-prompt-review-template.md) for the local review. It records current-version prompt approval before preflight with its own identity. Creating all children does not authorize images before their individual prompt approvals. The same child handles generation, labels, QA, image approval, matching video prompt and delivery. Saving files does not wake an idle conversation; use authorized coordination when needed and reread current state. Duplicate notifications never authorize another generation.

## Project membership when creating conversations

An independent shot conversation is a separate chat, not a separate Codex project. Apply this rule to every authorized new shot conversation: first all/pilot launch, later batches, replacements and legacy projects without the handoff marker. It does not authorize extra conversations or change the single/fast routes.

Before `create_thread`, resolve the coordinator's current app membership using its runtime-provided thread identity (for example `CODEX_THREAD_ID`) and host. Never choose by title, recency, working/output directory, storyboard `project.json`, or sidebar section. `list_threads` can omit new chats and can return `projectId: null` for a chat with an explicit desktop project assignment. A null value alone therefore does NOT establish projectless membership.

For the local desktop, run the read-only adapter for the exact coordinator ID before creation, and for each real child ID after creation:

```bash
python scripts/chat_membership.py --thread-id <exact-thread-id> --host-id local
```

It reads only explicit assignment/projectless entries in `$CODEX_HOME/.codex-global-state.json` (default `~/.codex`), outputs only the requested chat's result, and never modifies app state. This is a desktop compatibility adapter, not a stable public API. Unsupported/missing/conflicting state returns `unknown` with exit code 2; never treat failure as projectless. It supports local desktop state only, not remote/cloud membership. Do not copy or edit the desktop state, use backup files, or infer membership from workspace hints. For `project`, verify its returned ID against current `list_projects` on the same host before using it.

Also consult the exact `list_threads` record (including pinned threads, at most `limit: 50`). A non-null project matching `list_projects` can resolve membership when the adapter is unavailable. A missing record or null list value does not override an explicit desktop assignment. A different non-null project, or non-null project versus explicit desktop projectless, is a real conflict: reread once and stop if unresolved. If neither source resolves membership, ask one short question rather than guessing. A user's explicit destination also resolves the creation target after checking `list_projects`; it is not permission to rewrite the parent's membership.

| Verified coordinator membership | Default `create_thread.target` |
| --- | --- |
| A non-null Codex `projectId`, verified against `list_projects` on the matching host | `{"type":"project","projectId":"<verified-project-id>","environment":{"type":"local"}}` |
| Explicit desktop projectless entry, or the user's explicit projectless destination | `{"type":"projectless"}` |
| Unknown, conflicting, or an unavailable project | Do not create; finish read-only checks, then ask one short question if still unresolved. Do not fall back to projectless or another project. |

Unless the user explicitly chooses a different destination, keep the same project ID or projectless state. Resolve an explicitly chosen project through `list_projects` too. Default to the saved project's local environment; do not create a worktree or switch to cloud work without an explicit request. Keep absolute source/output paths in the task brief unchanged: those paths do not determine app membership, and projectless chats need not share the same working directory.

After creation returns a real `threadId` and available `hostId`, use the same adapter/source rules to compare the child's membership with the verified target before `register-task` and identity handoff. A missing list entry does not block a child whose explicit desktop assignment matches. A pending `clientThreadId` is not enough. If both sources are unavailable, recheck once; still unknown or explicitly different means report the exact chat and stop its handoff. Do not automatically repeat creation, move/rebuild/archive it, or claim that an output path proves membership. Preserve the actual creation target and returned IDs in the handoff note for recovery; never reconstruct the target from the intended plan. A success receipt proves creation, not independently verified membership. Previously paused chats created with the wrong target must not be released under this fix; any relocation/replacement needs the user's authorization.

This is a creation-time check, not ongoing coordinator monitoring or a new user approval. App membership remains sourced from app tools and explicit desktop records; the workflow state machine is unchanged, and no duplicate membership field is added to `project.json`.

## Shot task in the creative-plan handoff

After the full creative plan is approved, the shared brief and assigned sources are ready, and all/pilot launch is recorded, resolve the destination above and prepare the initial brief before creating a task:

```bash
python scripts/workflow.py task-brief <project> <shot-id>
```

Use that output as the initial brief. It points to the approved inputs and local files:

- `shared-brief.md` for global rules;
- `content-plan.json` for this shot's confirmed creative assignment and the batch context;
- the matching `shots/<shot-id>/shot.json` for local state;
- `project.json` for common settings;
- this shot's `storyboard-prompt.md` as the output to prepare, not a required existing input;
- the child presentation template and technical prompt reference linked by the task brief.

The child reads the whole plan, not just an isolated shot summary. After identity handoff, it writes its initial technical prompt and corresponding shot content from the complete approved panel text and scales, checks the actual prompt and batch context, enters `storyboard_prompt_pending`, and runs `prepare-prompt-review`. Render its bound content using the six-column child template, link the saved full prompt and wait for confirmation. Do not omit person actions or invent missing design choices. Existing valid prompts/reviews are preserved on resume, not redrafted merely because a child starts. The child owns all local revisions, images, labels, QA, image/video reviews and delivery. Save through `content-revision` / `save-content --expected-hash`; do not directly overwrite shared files or edit another shot / `project.json`. A user-requested local creative revision may update only its own plan entry after `revise ... storyboard_prompt`, using fresh whole-file read/merge/CAS; renew affected design approval, plan check and prompt review locally. Recheck global duplication but coordinate before changing other entries or global fields. Do not retry generation automatically.

## Record the launch after creative approval

For `creative_plan_to_shot`, the creative presentation explains that approval will create all staged children but not generate images. After the whole current design is approved and actual shared/reference material is ready, record `all` without asking a second question. If the user explicitly requests one or two pilot shots, record that instead and respect its selected scope. Full technical prompts and `check-prompt-plan` are required later before local prompt approval, not before child creation. This launch sets `video_prompt_owner: shot_task`.

Record the new model's default all launch (or an explicit all choice in older models) with:

```bash
python scripts/workflow.py set-concurrency <project> all
```

Record a pilot choice with either:

```bash
python scripts/workflow.py set-concurrency <project> pilot --count 1
python scripts/workflow.py set-concurrency <project> pilot --count 2
```

The script rejects registration while the launch is unset; record the approved scope rather than treating that error as a new all/pilot question in the creative model. `all` permits every staged shot; `pilot` permits only the selected one or two. Creating a task is not prompt approval. After a pilot, ask how the user wants to continue and record that choice after releasing active tasks; do not silently expand the cohort.

Pilot registration records the first 1–2 distinct shot IDs for that round. Releasing or approving one does not permit a new ID. The same shot may return for a user-requested new image in that round; an old-round shot cannot bypass a later pilot's scope. After explicit continuation, use `set-concurrency ... all --reason "actual decision"` or another requested pilot. Never reset the cohort on your own. A child with a current prompt review waits; one with valid complete content but no review submits it without rewriting; one in the new creative model without a prompt writes it from the approved design.

In a mixed-mode batch, these slots serve only staged shots; fast shots stay in the coordinator conversation and cannot register tasks. Release an active slot before switching its shot to fast. An unfinished revision to another shot does not block an already approved assignment, but global content-type/relationship changes require affected approvals to be renewed.

Registering a task activates a slot:

```bash
python scripts/workflow.py register-task <project> shot-01 <thread-id> --host-id <host-id>
```

The initial task brief and creative materials exist before the new task ID; only the older prepared model also requires a full prompt at that point. After a real `threadId` and available `hostId` return, verify project membership, register them, then pass that identity through authorized coordination. A pending `clientThreadId` is insufficient. Wait for identity and current prompt approval before preflight. Never copy the current owner from `project.json` as caller identity; a replaced task retains its own identity. Omit host at preflight only if registration omitted it. These internal details add no user questions.

A registration beyond the user-selected limit is rejected. If the old task has already started a generation, wait for its actual result or failure to be recorded before handing off; replacing the task does not cancel that call or grant a retry. Do not assign a different task to a shot that still has an active task: stop the old task first, then release its slot before registering the replacement. `release-task` updates the project record; it does not stop an external task by itself. A slot is released when the storyboard is approved, when manually released, or when the requested scope completes. Image-only approval completes the shot; combined delivery continues in the **same** shot conversation for video prompt and final delivery, retaining its thread/host identity but not occupying an active slot. To release a slot manually:

```bash
python scripts/workflow.py release-task <project> shot-01
```

Before each new staged generation, the assigned task runs:

```bash
python scripts/workflow.py preflight <project> shot-01 --thread-id <own-thread-id> --host-id <own-host-id>
```

Preflight checks launch permission and matches the supplied caller identity to the active registration before reserving a version. Missing or mismatched identity stops generation without claiming a version; refer the mismatch to the coordinator, rather than changing the caller ID to the current owner. This prevents accidental use of an old assignment, not deliberate impersonation. It does not check unrelated shot drafts. Once an image is approved, its video-prompt review uses an artifact review ID and does not require the released task to be reactivated. Later user-requested **image regeneration** does require an active registration and current all/pilot authorization again; retaining the old thread/host alone is insufficient. A new pilot round does not invalidate earlier approved images, but its scope controls new preflights.

Archiving a completed visible task is an optional UI action and requires the user's authorization when it has not already been requested.

When sidebar organization tools are available and the user explicitly requests organization, create one project-named section, pin or place the coordinator first, place the user-selected active shot tasks below it, and offer to archive completed shot tasks. A sidebar section is only organization, not Codex project membership, and cannot substitute for the creation-time check above. Do not change sidebar organization or archive tasks without that request.

## Existing prepared-prompt projects

Existing `prepared_prompt_to_shot` projects keep their original handoff, even before their first child or launch. The coordinator confirms designs with the established cadence, prepares every initial complete prompt and matching shot content, records each `check-prompt-plan`, then asks all-versus-pilot and records the user's choice. First launch, task brief and registration still require prepared current inputs in `storyboard_prompt_pending`. Children preserve those drafts, wait for real identity registration, review them locally and retain all later image/video work. Local creative revisions remain child-owned. Do not backfill the new marker, require six-column rewrites of valid older designs, or invalidate approvals just to adopt a new format.

## Existing projects without the handoff marker

Keep the original ownership, including projects that have not yet selected concurrency and v3 projects after explicit migration; migration does not add `handoff_model`. The coordinator confirms and owns the batch content plan, asks about all-versus-pilot before creating children, and retains global plan edits. Each registered shot task drafts its own first technical prompt and shot fields and returns them to the coordinator. The coordinator compares each returned prompt with the confirmed design and other shots, records `check-prompt-plan`, prepares and shows the prompt review, and records the user's version-specific approval. It then uses the authorized coordination mechanism to notify/resume the registered child; file approval alone does not wake it. The child rereads `task-brief` and the current approval and runs preflight with its own registered identity only if an unclaimed new generation is authorized. Duplicate notifications must not restart a claimed or completed attempt.

The child generates and QA-checks its image. After image approval releases the active slot, the existing coordinator route still owns the final video prompt and delivery aggregation. The original project does not acquire `video_prompt_owner: shot_task` merely by using new code. The new-model permission for a child to update its own content-plan entry does not apply to this legacy route; coordinate such design changes through the existing coordinator workflow. Other existing review IDs, preflight identity checks, retries and artifact bindings remain in force.

## Failures and retries

Failure stops the shot. Do not retry automatically, even for a severe objective defect. Show the failed output or concise failure report to the user. If the user explicitly requests another attempt, record the reason:

```bash
python scripts/workflow.py retry <project> shot-01 storyboard_generating \
  --reason "用户明确要求重新生成分镜"
```

Minor composition or packaging-text drift remains reviewable and does not trigger regeneration by itself.

For user-requested design swaps, stop/release only the affected tasks and use `revise-designs <project> <shot-id> ... --reason ...` before editing the group. It retires old assignments together without erasing their history. Reconfirm the affected designs; other shots retain their approvals. See execution.md for content saves and conflict recovery.
