# Storyboard project schema

## Layout

```text
project/
  project.json
  project.json.bak             # created only by explicit migration
  shared-brief.md              # coordinator-owned global rules
  sources/
  shots/
    shot-01/
      shot.json
      panels/
      storyboard-v01.png
      storyboard-review-v01.png
      video-prompt.md
      storyboard-final.png
```

`panels/` is an implementation detail used by deterministic layout. Strict mode may add audit files.

## project.json — schema version 4

```json
{
  "schema_version": 4,
  "name": "project-name",
  "defaults": {
    "ratio": "9:16",
    "layout": "2x2",
    "duration_seconds": 5,
    "duration_policy": {"minimum_seconds": 4, "typical_range_seconds": [5, 10]},
    "reading_order": ["top_left", "top_right", "bottom_left", "bottom_right"],
    "time_boundaries_seconds": [0, 1, 2.5, 4, 5],
    "time_ranges": ["0–1秒", "1–2.5秒", "2.5–4秒", "4–5秒"],
    "video_resolution": "1080p",
    "audio": "无对白、无旁白、仅极轻环境声"
  },
  "workflow": {
    "default_review_mode": "staged",
    "cross_shot_parallel": true,
    "approval": "storyboard_prompt_then_storyboard_then_video_prompt",
    "execution_model": "coordinator_with_shot_slots",
    "parallel_launch_mode": null,
    "max_parallel_shot_tasks": null,
    "shared_brief_path": "shared-brief.md",
    "retry_policy": "explicit_user_request_only",
    "video_prompt_owner": "coordinator",
    "one_visible_task_per_shot": true
  },
  "shots": [
    {
      "id": "shot-01",
      "title": "镜头名称",
      "status": "todo",
      "review_mode": "staged",
      "task": {"thread_id": null, "host_id": null, "active": false}
    }
  ]
}
```

The five numeric boundaries define exactly four continuous ranges. `workflow.py init --duration` derives them at 0%, 20%, 50%, 80%, and 100% of the approved duration. Every duration must be at least four seconds.

## shot.json

```json
{
  "shot_id": "shot-01",
  "title": "镜头名称",
  "status": "storyboard_review_pending",
  "review_mode": "staged",
  "review_mode_source": "default",
  "review_mode_reason": null,
  "retries": [],
  "approvals": [
    {
      "stage": "storyboard_prompt",
      "decision": "approved",
      "note": null,
      "recorded_at": "2026-09-22T00:00:00+00:00"
    }
  ],
  "references": [
    {"id": "image-01", "roles": ["product_identity", "structure_count"]},
    {"id": "image-02", "roles": ["background_lighting", "hand_action"]}
  ],
  "panels": [
    {"position": "top_left", "start_seconds": 0, "end_seconds": 1, "time": "0–1秒", "label": "外观展示", "description": "完整状态", "image": "panels/panel-01.png"},
    {"position": "top_right", "start_seconds": 1, "end_seconds": 2.5, "time": "1–2.5秒", "label": "结构特写", "description": "完整状态", "image": "panels/panel-02.png"},
    {"position": "bottom_left", "start_seconds": 2.5, "end_seconds": 4, "time": "2.5–4秒", "label": "使用细节", "description": "完整状态", "image": "panels/panel-03.png"},
    {"position": "bottom_right", "start_seconds": 4, "end_seconds": 5, "time": "4–5秒", "label": "产品定格", "description": "最终状态", "image": "panels/panel-04.png"}
  ],
  "camera": "<motion>",
  "must_keep": [],
  "forbidden": [],
  "qa": {"result": "pass_with_notes", "notes": []},
  "storyboard_version": 1
}
```

One reference may have one or a small number of roles. Keep the set minimal. Role values are `product_identity`, `structure_count`, `packaging_text`, `background_lighting`, `hand_action`, and `composition`.

## Review modes and statuses

Staged mode is the default. Canonical status flow:

```text
todo
→ storyboard_prompt_pending
→ storyboard_generating
→ storyboard_review_pending
→ video_prompt_pending
→ video_prompt_review_pending
→ complete
```

The three review transitions are advanced with `workflow.py approve`; ordinary `status` commands cannot jump across them. After storyboard approval, the shot-task slot is released and the coordinator owns video-prompt generation.

Fast mode is allowed only after an explicit user request is recorded with `set-mode --reason`:

```text
todo → running → review_pending → complete
```

Approve the combined package with the `review_package` stage.

Legacy statuses remain readable for schema v1–v3 projects. New schema v4 projects use only the canonical flows above.

## Coordination and retries

Concurrency begins unselected. Before creating tasks, ask whether to start all shots or pilot one or two, then run `set-concurrency <project> all` or `set-concurrency <project> pilot --count 1|2`. `register-task` is rejected until this decision is recorded and then permits at most `max_parallel_shot_tasks` active shot tasks. `release-task` frees a slot without deleting the saved thread ID. `dashboard` renders a compact project status table, and `task-brief` emits the short file-based instruction for one shot.

Failure statuses have no normal outgoing transition. `retry` requires a non-empty explicit user reason, records it in `shot.json.retries`, and then returns the shot to its generation state. Neither severe nor minor defects trigger an automatic retry.

## Migration

`workflow.py validate` never changes a project. Run `workflow.py migrate <project>` explicitly to migrate schema v3 to v4. Migration:

- creates `project.json.bak` and refuses to overwrite an existing backup;
- derives numeric time boundaries from the existing duration;
- infers `fast` only for existing fast-mode statuses;
- adds empty approval history without inventing past approvals;
- creates `shared-brief.md`, leaves concurrency unselected so the user is asked before task creation, and adds empty retry history;
- preserves sources, hashes, task IDs, shot titles, and current statuses.

Schema v1 and v2 remain readable but are not automatically migrated.
