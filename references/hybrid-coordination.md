# Hybrid coordinator and shot-task workflow

Use this reference for staged requests for two or more storyboard images. The coordinator and separate shot conversations are the staged multi-image route. New projects marked `workflow.handoff_model: prepared_prompt_to_shot` use the prepared-prompt handoff below. An existing project without this marker, even if concurrency has not yet been chosen, keeps the legacy coordinator-led prompt approval and video-prompt workflow described at the end; do not infer the new model from shot count or silently add the marker. Explicit fast-mode or direct-generation requests instead stay in the current conversation; follow [execution.md](execution.md). If the user gives no quantity, default to one storyboard image. For a single image, keep prompt confirmation and all later review in the current conversation; skip coordinator/shot-task design and concurrency selection.

Use one coordinator conversation plus a user-selected set of active shot conversations. Do not impose a two-task default.

This follows [OpenAI's long-running work guidance](https://learn.chatgpt.com/docs/long-running-work): keep related work in one chat for shared context and use separate chats only when tasks can run independently.

## New prepared-prompt handoff: coordinator ownership

For a new marked multi-shot staged project, the coordinator owns:

- `shared-brief.md` and global visual rules;
- initial `content-plan.json`: the story/showcase decision, verified use contexts and selling points, four short beats and shot scales per image, and cross-shot diversity;
- `project.json`, stabilized sources, task registration, and the dashboard;
- writing every shot's initial complete `storyboard-prompt.md` and matching `shot.json` content after creative confirmation; checking each against its confirmed design and the whole batch with `check-prompt-plan`;
- only after all initial prompts and checks are ready, asking whether to start every shot or pilot one or two shots first, then recording that choice and creating shot conversations;
- maintaining global settings, source assets and cross-shot coordination when a change genuinely affects more than one shot.

The coordinator does not routinely submit a shot's prompt review, approve its image, write its video prompt, or aggregate its delivery. Each new-model shot conversation owns those local steps through completion. `video_prompt_owner: shot_task` records this ownership after concurrency is chosen; it is not a new user checkpoint or a permission system.

Plan the whole batch internally before showing one image at a time to the user. If the relationship is unclear, ask whether the images form one continuous video or independent options. For a continuous video, give one short overall progression first. Confirm each image's context, main selling point, and four one-sentence beats; if earlier feedback changes a later image, revise the unconfirmed images. After all are confirmed, compare opening, action and ending motifs across the batch. Show only necessary local changes for renewed confirmation. Use `approval_source: explicit_fast_request` only for an explicit fast request; plain “生成” remains staged. Keep the content plan's confirmation text grounded in the user's actual reply.

When the user asks for overall progress, read `workflow.py dashboard <project>` on demand. Do not turn it into routine coordinator status collection, per-shot approval relay or final delivery aggregation. Shots do not need to remain synchronized.

Before showing each creative design, run `prepare-design-review`; after the user's reply, record `approve-design` with its current ID and actual confirmation. A saved confirmation sentence alone is not authorization. Then complete every initial prompt and matching shot fields. The coordinator actually compares prompt, confirmed design, and cross-shot opening/action/ending, recording a concrete `check-prompt-plan --note ...` for every shot **before** asking about concurrency. See [execution.md](execution.md). Do not create a child merely to draft or return a prompt.

The new-model handoff gives the child the existing prompt, then the coordinator verifies its project membership, registers its real thread/host identity and tells that child its own identity. The child waits for this registration **before** running `prepare-prompt-review` or showing its first prompt review. It then submits the saved prompt, waits for the user's current-version confirmation, records `approve ... storyboard_prompt`, and runs preflight with its own identity when generation is authorized and unclaimed. The same shot conversation generates, locally labels and visually checks the image, presents it for approval, writes and reviews any matching video prompt, and delivers its result. Saving local files does not wake an idle conversation: when a continuation is needed, use the existing authorized coordination mechanism and have the task reread current state. Duplicate notifications never authorize another generation.

## Project membership when creating conversations

An independent shot conversation is a separate chat, not a separate Codex project. Apply this rule to every authorized new shot conversation: first all/pilot launch, later batches, replacements and legacy projects without the handoff marker. It does not authorize extra conversations or change the single/fast routes.

Before `create_thread`, resolve the coordinator's current app membership. Use its runtime-provided thread identity (for example `CODEX_THREAD_ID`, when available) and host to match the exact record in `list_threads`, including pinned threads. If absent from a limited result, broaden the read-only lookup; do not choose a similarly named or recently active chat. Do not infer membership from the working directory, output directory, storyboard `project.json`, or sidebar section. A missing record/field is unknown, not an explicit `projectId: null`.

| Verified coordinator membership | Default `create_thread.target` |
| --- | --- |
| A non-null Codex `projectId`, verified against `list_projects` on the matching host | `{"type":"project","projectId":"<verified-project-id>","environment":{"type":"local"}}` |
| The exact app record explicitly has `projectId: null` | `{"type":"projectless"}` |
| Unknown, conflicting, or an unavailable project | Do not create; finish read-only checks, then ask one short question if still unresolved. Do not fall back to projectless or another project. |

Unless the user explicitly chooses a different destination, keep the same project ID or projectless state. Resolve an explicitly chosen project through `list_projects` too. Default to the saved project's local environment; do not create a worktree or switch to cloud work without an explicit request. Keep absolute source/output paths in the task brief unchanged: those paths do not determine app membership, and projectless chats need not share the same working directory.

After creation returns a real `threadId` and available `hostId`, read the exact child's app record and check its `projectId` against the intended destination (including explicit null for projectless) before `register-task` and identity handoff. A pending `clientThreadId` is not enough. If the record is not yet visible, make a bounded read-only recheck. If membership remains unknown or differs, report the created chat and stop its handoff; do not register it, automatically repeat creation, move/rebuild/archive it, or claim that a correct output path proves success. An ambiguous creation result likewise does not authorize another creation attempt. Existing chats are not automatically relocated by this rule.

This is a creation-time check, not ongoing coordinator monitoring or a new user approval. App membership remains sourced from the app; the local workflow CLI does not validate it, and no duplicate membership field is added to `project.json`.

## Shot task in the new handoff

After the existing preparation and launch-choice requirements are satisfied, resolve the creation destination as above and prepare the initial brief before creating a shot task:

```bash
python scripts/workflow.py task-brief <project> <shot-id>
```

Use that output as the shot task's initial brief. For the new handoff it points to already-prepared materials:

- `shared-brief.md` for global rules;
- `content-plan.json` for this shot's confirmed creative assignment and the batch context;
- the matching `shots/<shot-id>/shot.json` for local state;
- `project.json` for common settings.
- this shot's complete `storyboard-prompt.md` and populated local shot content.

The new-model shot task first reads and preserves its assigned complete prompt; do not rewrite it on receipt. Once its real task identity has been registered and handed to it, it runs `prepare-prompt-review`, shows the concise plan and links that saved prompt in its own conversation, waits for the user's confirmation, and records approval there. A still-valid review resumed after interruption is shown/waited on, not recreated. Thereafter it owns its own prompt revisions, image generation, local labels, QA, image review, video prompt (if in scope), and delivery. Save changes via `content-revision` / `save-content --expected-hash`; never overwrite shared targets directly. It must not edit another shot or `project.json`. A user-requested creative revision confined to this shot may update **only its own entry** of `content-plan.json` after `revise ... storyboard_prompt`, using a fresh whole-file read, merge and compare-and-save; then renew this shot's design confirmation, prompt-plan check and prompt review locally. Do not alter global plan fields or other entries; refer genuine global or cross-shot changes for explicit coordination. Workflow commands lock and update manifests with recovery. Do not retry automatically.

## Choose concurrency after initial prompt preparation

After the shared brief, complete content plan, every staged creative design confirmation, every complete initial prompt and its shot content, and every initial `check-prompt-plan` are ready, ask one concise question: “要直接同时开始全部镜头，还是先做 1–2 个镜头确认效果？” Do not create any shot task until the user answers. This new-model choice records `video_prompt_owner: shot_task`; shot tasks receive prompts rather than writing their first versions.

Record “全部开始” with:

```bash
python scripts/workflow.py set-concurrency <project> all
```

Record a pilot choice with either:

```bash
python scripts/workflow.py set-concurrency <project> pilot --count 1
python scripts/workflow.py set-concurrency <project> pilot --count 2
```

The script rejects task registration while this choice is unset. `all` permits every project shot to start; `pilot` permits only the selected one or two shots. A pilot is not a permanent project-wide ceiling: after the user reviews the effect, ask how they want to continue and update the choice after releasing active tasks.

Pilot registration records the first 1–2 distinct shot IDs for that round. Releasing or approving a pilot shot does not permit a new ID. In the same round, the same shot may return for a user-requested new image; once a later pilot round selects different shots, an old-round shot cannot bypass that current scope. After the user's explicit continuation decision, use `set-concurrency ... all --reason "actual decision"` or a new `pilot --count ... --reason ...`. Never reset the cohort on your own. A child with a current prompt-review record waits for confirmation; one with a valid handed-off prompt but no review submits it rather than rewriting it.

In a mixed-mode batch, these slots serve only staged shots; fast shots stay in the coordinator conversation and cannot register tasks. Release an active slot before switching its shot to fast. An unfinished revision to another shot does not block an already approved assignment, but global content-type/relationship changes require affected approvals to be renewed.

Registering a task activates a slot:

```bash
python scripts/workflow.py register-task <project> shot-01 <thread-id> --host-id <host-id>
```

The initial brief and complete prompt are prepared before the new task ID exists. After creation returns a real `threadId` and its `hostId` when available, complete the project-membership check above, register them, then pass that identity to the assigned task through the authorized coordination workflow. A pending `clientThreadId` is not a usable thread ID. The task waits for its own identity and the current prompt approval before preflight. Never infer caller identity by copying the current owner from `project.json`; a replaced task must retain its own old identity. If no host was supplied at registration, omit `--host-id` at preflight too; otherwise pass the exact registered host. These are internal handoff details, not new user questions.

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
