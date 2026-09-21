# Fast project schema

## Layout

```text
project/
  project.json
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

## project.json — schema version 3

```json
{
  "schema_version": 3,
  "name": "project-name",
  "defaults": {
    "ratio": "9:16",
    "layout": "2x2",
    "duration_seconds": 5,
    "duration_policy": {"minimum_seconds": 4, "typical_range_seconds": [5, 10]},
    "reading_order": ["top_left", "top_right", "bottom_left", "bottom_right"],
    "time_ranges": ["0–1秒", "1–2.5秒", "2.5–4秒", "4–5秒"],
    "video_resolution": "1080p",
    "audio": "无对白、无旁白、仅极轻环境声"
  },
  "workflow": {
    "mode": "staged_customer_review",
    "cross_shot_parallel": true,
    "approval": "storyboard_prompt_then_storyboard_then_video_prompt",
    "one_visible_task_per_shot": true
  },
  "shots": [
    {
      "id": "shot-01",
      "title": "镜头名称",
      "status": "todo",
      "task": {"thread_id": null, "host_id": null}
    }
  ]
}
```

Default staged statuses: `todo`, `storyboard_prompt_pending`, `storyboard_generating`, `storyboard_pending`, `storyboard_review_pending`, `video_prompt_pending`, `video_prompt_review_pending`, `complete`, `generation_failed`.

Fast-mode compatibility statuses remain readable: `running`, `review_pending`, `failed`.

## shot.json

```json
{
  "shot_id": "shot-01",
  "title": "镜头名称",
  "status": "review_pending",
  "references": [
    {"id": "image-01", "roles": ["product_identity", "structure_count"]},
    {"id": "image-02", "roles": ["background_lighting", "hand_action"]}
  ],
  "panels": [
    {"position": "top_left", "time": "0–1秒", "label": "外观展示", "description": "完整状态", "image": "panels/panel-01.png"},
    {"position": "top_right", "time": "1–2.5秒", "label": "结构特写", "description": "完整状态", "image": "panels/panel-02.png"},
    {"position": "bottom_left", "time": "2.5–4秒", "label": "使用细节", "description": "完整状态", "image": "panels/panel-03.png"},
    {"position": "bottom_right", "time": "4–5秒", "label": "产品定格", "description": "最终状态", "image": "panels/panel-04.png"}
  ],
  "camera": "<motion>",
  "must_keep": [],
  "forbidden": [],
  "qa": {"result": "pass_with_notes", "notes": []},
  "storyboard_version": 1
}
```

Role values: `product_identity`, `structure_count`, `packaging_text`, `background_lighting`, `hand_action`, `composition`.

The shot task owns `shot.json`. The coordinator runs `workflow.py sync` to update only the matching summary row in `project.json`. Schema v1 and v2 remain readable for existing projects.
