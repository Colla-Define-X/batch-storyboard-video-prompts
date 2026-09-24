# Hybrid coordinator and shot-task workflow

Use this reference only when the user requests two or more storyboard images and separate shot conversations are appropriate. If the user gives no quantity, default to one storyboard image. For a single image, keep prompt confirmation and all later review in the current conversation; skip coordinator/shot-task design and concurrency selection.

Use one coordinator conversation plus a user-selected set of active shot conversations. Do not impose a two-task default.

This follows [OpenAI's long-running work guidance](https://learn.chatgpt.com/docs/long-running-work): keep related work in one chat for shared context and use separate chats only when tasks can run independently.

## Coordinator ownership

The coordinator alone owns:

- `shared-brief.md` and global visual rules;
- `project.json`, stabilized sources, task registration, and the dashboard;
- asking whether to start every shot or pilot one or two shots first, then recording that choice;
- final video-prompt generation and final delivery aggregation.

Run `workflow.py dashboard <project>` to show current per-shot progress. Shots do not need to remain synchronized.

## Lightweight shot task

Before creating a shot task, run:

```bash
python scripts/workflow.py task-brief <project> <shot-id>
```

Send only that output to the shot task. It points to:

- `shared-brief.md` for global rules;
- the matching `shots/<shot-id>/shot.json` for local state;
- `project.json` for common settings.

The shot task owns content for its assigned shot and must not edit another shot or manually edit project.json. Workflow commands lock and update both manifests with recovery. The coordinator owns shared-brief.md, source/task registration and final video prompts. Do not retry automatically. A fast combined-delivery shot returns its reviewed image while still running; the coordinator adds the video prompt then enters review_pending.

## Choose concurrency before task creation

After the shared brief and shot prompts are ready, ask one concise question: “要直接同时开始全部镜头，还是先做 1–2 个镜头确认效果？” Do not create any shot task until the user answers.

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

Registering a task activates a slot:

```bash
python scripts/workflow.py register-task <project> shot-01 <thread-id> --host-id <host-id>
```

A registration beyond the user-selected limit is rejected. A slot is released when the storyboard is approved, when manually released, or when the requested scope completes. Image-only approval completes the shot; combined delivery returns for the video prompt:

```bash
python scripts/workflow.py release-task <project> shot-01
```

Archiving a completed visible task is an optional UI action and requires the user's authorization when it has not already been requested.

When sidebar organization tools are available and the user explicitly requests organization, create one project-named section, pin or place the coordinator first, place the user-selected active shot tasks below it, and offer to archive completed shot tasks. Do not change sidebar organization or archive tasks without that request.

## Failures and retries

Failure stops the shot. Do not retry automatically, even for a severe objective defect. Show the failed output or concise failure report to the user. If the user explicitly requests another attempt, record the reason:

```bash
python scripts/workflow.py retry <project> shot-01 storyboard_generating \
  --reason "用户明确要求重新生成分镜"
```

Minor composition or packaging-text drift remains reviewable and does not trigger regeneration by itself.

## Single-conversation option

If the user prioritizes minimum usage, keep all shots in the coordinator conversation. Read each `shot.json`, advance every approved next step in one turn, and allow shots to remain at different statuses. This preserves independent state and review gates but is coordinated work inside one conversation, not true independent background parallelism.
